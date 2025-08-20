from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext as _
import time
import hashlib
from .models import SecurityLog, SuspiciousActivity
from .utils import get_client_ip, get_location_from_ip


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Güvenlik başlıklarını otomatik olarak ekleyen middleware
    """
    
    def process_response(self, request, response):
        # Content Security Policy
        if hasattr(settings, 'CSP_DEFAULT_SRC'):
            csp_parts = []
            csp_parts.append(f"default-src {settings.CSP_DEFAULT_SRC}")
            
            if hasattr(settings, 'CSP_SCRIPT_SRC'):
                csp_parts.append(f"script-src {settings.CSP_SCRIPT_SRC}")
            if hasattr(settings, 'CSP_STYLE_SRC'):
                csp_parts.append(f"style-src {settings.CSP_STYLE_SRC}")
            if hasattr(settings, 'CSP_IMG_SRC'):
                csp_parts.append(f"img-src {settings.CSP_IMG_SRC}")
            if hasattr(settings, 'CSP_FONT_SRC'):
                csp_parts.append(f"font-src {settings.CSP_FONT_SRC}")
            if hasattr(settings, 'CSP_CONNECT_SRC'):
                csp_parts.append(f"connect-src {settings.CSP_CONNECT_SRC}")
            if hasattr(settings, 'CSP_FRAME_ANCESTORS'):
                csp_parts.append(f"frame-ancestors {settings.CSP_FRAME_ANCESTORS}")
            
            response['Content-Security-Policy'] = '; '.join(csp_parts)
        
        # Diğer güvenlik başlıkları
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = getattr(settings, 'SECURE_REFERRER_POLICY', 'strict-origin-when-cross-origin')
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # HSTS başlığı (sadece HTTPS için)
        if request.is_secure() and hasattr(settings, 'SECURE_HSTS_SECONDS'):
            hsts_header = f'max-age={settings.SECURE_HSTS_SECONDS}'
            if getattr(settings, 'SECURE_HSTS_INCLUDE_SUBDOMAINS', False):
                hsts_header += '; includeSubDomains'
            if getattr(settings, 'SECURE_HSTS_PRELOAD', False):
                hsts_header += '; preload'
            response['Strict-Transport-Security'] = hsts_header
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware - IP bazlı istek sınırlaması
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit_cache = {}  # Basit in-memory cache
        super().__init__(get_response)
    
    def process_request(self, request):
        # Admin paneli ve statik dosyalar için rate limiting uygulanmaz
        if (request.path.startswith('/admin/') or 
            request.path.startswith('/static/') or 
            request.path.startswith('/media/')):
            return None
        
        client_ip = get_client_ip(request)
        current_time = time.time()
        
        # Rate limit ayarları
        window_size = 60  # 1 dakika
        max_requests = 100  # Dakikada maksimum 100 istek
        
        # Cache temizleme (eski kayıtları sil)
        self.cleanup_cache(current_time, window_size)
        
        # IP için istek sayısını kontrol et
        if client_ip not in self.rate_limit_cache:
            self.rate_limit_cache[client_ip] = []
        
        # Son dakikadaki istekleri say
        recent_requests = [
            req_time for req_time in self.rate_limit_cache[client_ip]
            if current_time - req_time < window_size
        ]
        
        if len(recent_requests) >= max_requests:
            # Rate limit aşıldı
            SecurityLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                event_type='rate_limit_exceeded',
                ip_address=client_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details=f'Rate limit exceeded: {len(recent_requests)} requests in {window_size} seconds'
            )
            
            # Şüpheli aktivite kaydı
            SuspiciousActivity.objects.create(
                user=request.user if request.user.is_authenticated else None,
                activity_type='rate_limit_violation',
                ip_address=client_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                severity='medium',
                details=f'Rate limit exceeded: {len(recent_requests)} requests',
                location_data=get_location_from_ip(client_ip)
            )
            
            return HttpResponse(
                'Rate limit exceeded. Please try again later.',
                status=429,
                content_type='text/plain'
            )
        
        # İsteği kaydet
        self.rate_limit_cache[client_ip].append(current_time)
        
        return None
    
    def cleanup_cache(self, current_time, window_size):
        """
        Eski cache kayıtlarını temizle
        """
        for ip in list(self.rate_limit_cache.keys()):
            self.rate_limit_cache[ip] = [
                req_time for req_time in self.rate_limit_cache[ip]
                if current_time - req_time < window_size
            ]
            
            # Boş listeler için IP'yi sil
            if not self.rate_limit_cache[ip]:
                del self.rate_limit_cache[ip]


class SuspiciousActivityMiddleware(MiddlewareMixin):
    """
    Şüpheli aktiviteleri tespit eden middleware
    """
    
    def process_request(self, request):
        # Admin paneli için şüpheli aktivite kontrolü yapılmaz
        if request.path.startswith('/admin/'):
            return None
        
        client_ip = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Şüpheli user agent kontrolü
        suspicious_agents = [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
            'python-requests', 'libwww', 'lwp-trivial'
        ]
        
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            self.log_suspicious_activity(
                request, 'suspicious_user_agent',
                f'Suspicious user agent detected: {user_agent}',
                'low'
            )
        
        # SQL injection girişimi kontrolü
        query_params = request.GET.urlencode() + request.POST.urlencode()
        sql_patterns = [
            'union select', 'drop table', 'insert into', 'delete from',
            'update set', 'exec(', 'script>', '<iframe', 'javascript:'
        ]
        
        if any(pattern in query_params.lower() for pattern in sql_patterns):
            self.log_suspicious_activity(
                request, 'sql_injection_attempt',
                f'Potential SQL injection detected in parameters',
                'high'
            )
        
        # Çok fazla 404 hatası kontrolü
        if hasattr(request, 'resolver_match') and request.resolver_match is None:
            self.check_404_abuse(request, client_ip)
        
        return None
    
    def log_suspicious_activity(self, request, activity_type, details, severity):
        """
        Şüpheli aktiviteyi logla
        """
        client_ip = get_client_ip(request)
        
        SecurityLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            event_type='suspicious_activity_detected',
            ip_address=client_ip,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details=details
        )
        
        SuspiciousActivity.objects.create(
            user=request.user if request.user.is_authenticated else None,
            activity_type=activity_type,
            ip_address=client_ip,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            severity=severity,
            details=details,
            location_data=get_location_from_ip(client_ip)
        )
    
    def check_404_abuse(self, request, client_ip):
        """
        404 abuse kontrolü
        """
        from django.utils import timezone
        from datetime import timedelta
        
        # Son 10 dakikada bu IP'den kaç 404 hatası olduğunu kontrol et
        recent_404s = SecurityLog.objects.filter(
            ip_address=client_ip,
            event_type='page_not_found',
            timestamp__gte=timezone.now() - timedelta(minutes=10)
        ).count()
        
        if recent_404s >= 20:  # 10 dakikada 20'den fazla 404
            self.log_suspicious_activity(
                request, 'excessive_404_requests',
                f'Excessive 404 requests: {recent_404s} in 10 minutes',
                'medium'
            )


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Oturum güvenliği middleware'i
    """
    
    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        
        # Oturum hijacking kontrolü
        session_ip = request.session.get('session_ip')
        current_ip = get_client_ip(request)
        
        if session_ip and session_ip != current_ip:
            # IP değişikliği tespit edildi
            SecurityLog.objects.create(
                user=request.user,
                event_type='session_ip_change',
                ip_address=current_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details=f'Session IP changed from {session_ip} to {current_ip}'
            )
            
            # Şüpheli aktivite kaydı
            SuspiciousActivity.objects.create(
                user=request.user,
                activity_type='session_hijacking_attempt',
                ip_address=current_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                severity='high',
                details=f'Session IP changed from {session_ip} to {current_ip}',
                location_data=get_location_from_ip(current_ip)
            )
            
            # Oturumu sonlandır
            from django.contrib.auth import logout
            logout(request)
            messages.error(request, _('Güvenlik nedeniyle oturumunuz sonlandırıldı.'))
            return redirect('accounts:login')
        
        # İlk kez IP kaydet
        if not session_ip:
            request.session['session_ip'] = current_ip
        
        # Oturum aktivitesini güncelle
        request.session['last_activity'] = time.time()
        
        return None