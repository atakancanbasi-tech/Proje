from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from .models import EmailVerificationCode, SecurityLog, AccountLockout, UserSecuritySettings
import random
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """İstemci IP adresini al"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Kullanıcı agent bilgisini al"""
    return request.META.get('HTTP_USER_AGENT', '')[:500]  # Maksimum 500 karakter


def generate_captcha():
    """Basit matematik CAPTCHA oluştur"""
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    operation = random.choice(['+', '-', '*'])
    
    if operation == '+':
        answer = num1 + num2
        question = f"{num1} + {num2} = ?"
    elif operation == '-':
        # Negatif sonuç olmasın diye büyük sayıyı önce koy
        if num1 < num2:
            num1, num2 = num2, num1
        answer = num1 - num2
        question = f"{num1} - {num2} = ?"
    else:  # multiplication
        answer = num1 * num2
        question = f"{num1} × {num2} = ?"
    
    return question, answer


def send_verification_email(user, code_type, verification_code, request=None):
    """Doğrulama e-postası gönder"""
    try:
        # E-posta şablonu seç
        if code_type == '2fa':
            subject = 'İki Faktörlü Kimlik Doğrulama Kodu'
            template = 'security/emails/2fa_code.html'
        elif code_type == 'password_reset':
            subject = 'Şifre Sıfırlama Kodu'
            template = 'security/emails/password_reset_code.html'
        elif code_type == 'email_change':
            subject = 'E-posta Değişikliği Doğrulama Kodu'
            template = 'security/emails/email_change_code.html'
        else:
            subject = 'Hesap Doğrulama Kodu'
            template = 'security/emails/account_verification_code.html'
        
        # E-posta içeriği
        context = {
            'user': user,
            'verification_code': verification_code.code,
            'expires_at': verification_code.expires_at,
            'code_type': code_type,
            'site_name': 'Satış Sitesi'
        }
        
        html_message = render_to_string(template, context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[verification_code.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Verification email sent to {user.username} ({verification_code.email}) for {code_type}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.username}: {str(e)}")
        return False


def send_security_alert_email(user, event_type, description, request=None):
    """Güvenlik uyarısı e-postası gönder"""
    try:
        # Kullanıcının güvenlik ayarlarını kontrol et
        try:
            settings_obj = UserSecuritySettings.objects.get(user=user)
            if not settings_obj.suspicious_activity_alerts:
                return True  # Kullanıcı uyarı almak istemiyor
        except UserSecuritySettings.DoesNotExist:
            pass  # Varsayılan olarak uyarı gönder
        
        subject = 'Güvenlik Uyarısı - Hesabınızda Şüpheli Aktivite'
        
        context = {
            'user': user,
            'event_type': event_type,
            'description': description,
            'timestamp': timezone.now(),
            'ip_address': get_client_ip(request) if request else 'Bilinmiyor',
            'site_name': 'Satış Sitesi'
        }
        
        html_message = render_to_string('security/emails/security_alert.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Security alert email sent to {user.username} for {event_type}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send security alert email to {user.username}: {str(e)}")
        return False


def send_login_notification_email(user, request=None):
    """Giriş bildirimi e-postası gönder"""
    try:
        # Kullanıcının güvenlik ayarlarını kontrol et
        try:
            settings_obj = UserSecuritySettings.objects.get(user=user)
            if not settings_obj.login_notifications:
                return True  # Kullanıcı bildirim almak istemiyor
        except UserSecuritySettings.DoesNotExist:
            pass  # Varsayılan olarak bildirim gönder
        
        subject = 'Hesabınıza Giriş Yapıldı'
        
        context = {
            'user': user,
            'timestamp': timezone.now(),
            'ip_address': get_client_ip(request) if request else 'Bilinmiyor',
            'user_agent': get_user_agent(request) if request else 'Bilinmiyor',
            'site_name': 'Satış Sitesi'
        }
        
        html_message = render_to_string('security/emails/login_notification.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Login notification email sent to {user.username}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send login notification email to {user.username}: {str(e)}")
        return False


def check_failed_login_attempts(user, request=None):
    """Başarısız giriş denemelerini kontrol et ve gerekirse hesabı kilitle"""
    ip_address = get_client_ip(request) if request else None
    
    # Son 15 dakikadaki başarısız giriş denemelerini say
    since = timezone.now() - timedelta(minutes=15)
    failed_attempts = SecurityLog.objects.filter(
        user=user,
        event_type='login_failed',
        created_at__gte=since
    ).count()
    
    # 5 başarısız denemeden sonra hesabı kilitle
    if failed_attempts >= 5:
        lockout = AccountLockout.lock_account(
            user=user,
            reason='failed_login',
            duration_minutes=30,  # 30 dakika kilitle
            ip_address=ip_address,
            description=f'5 başarısız giriş denemesi (son 15 dakika)'
        )
        
        # Güvenlik uyarısı gönder
        send_security_alert_email(
            user=user,
            event_type='account_locked',
            description='Çoklu başarısız giriş denemesi nedeniyle hesabınız geçici olarak kilitlendi.',
            request=request
        )
        
        return True  # Hesap kilitlendi
    
    return False  # Hesap kilitlenmedi


def check_failed_2fa_attempts(user, request=None):
    """Başarısız 2FA denemelerini kontrol et"""
    ip_address = get_client_ip(request) if request else None
    
    # Son 10 dakikadaki başarısız 2FA denemelerini say
    since = timezone.now() - timedelta(minutes=10)
    failed_attempts = SecurityLog.objects.filter(
        user=user,
        event_type='2fa_failed',
        created_at__gte=since
    ).count()
    
    # 3 başarısız denemeden sonra hesabı kilitle
    if failed_attempts >= 3:
        lockout = AccountLockout.lock_account(
            user=user,
            reason='failed_2fa',
            duration_minutes=60,  # 1 saat kilitle
            ip_address=ip_address,
            description=f'3 başarısız 2FA denemesi (son 10 dakika)'
        )
        
        # Güvenlik uyarısı gönder
        send_security_alert_email(
            user=user,
            event_type='account_locked',
            description='Çoklu başarısız iki faktörlü kimlik doğrulama denemesi nedeniyle hesabınız geçici olarak kilitlendi.',
            request=request
        )
        
        return True  # Hesap kilitlendi
    
    return False  # Hesap kilitlenmedi


def is_account_locked(user):
    """Hesabın kilitli olup olmadığını kontrol et"""
    try:
        lockout = AccountLockout.objects.get(user=user)
        return lockout.is_locked()
    except AccountLockout.DoesNotExist:
        return False


def detect_suspicious_activity(user, request=None):
    """Şüpheli aktivite tespiti"""
    ip_address = get_client_ip(request) if request else None
    
    # Son 1 saatteki giriş denemelerini kontrol et
    since = timezone.now() - timedelta(hours=1)
    recent_logins = SecurityLog.objects.filter(
        user=user,
        event_type__in=['login_success', 'login_failed'],
        created_at__gte=since
    )
    
    # Farklı IP adreslerinden giriş kontrolü
    ip_addresses = set(log.ip_address for log in recent_logins if log.ip_address)
    
    if len(ip_addresses) > 3:  # 1 saat içinde 3'ten fazla farklı IP
        SecurityLog.log_event(
            event_type='suspicious_activity',
            user=user,
            ip_address=ip_address,
            description=f'1 saat içinde {len(ip_addresses)} farklı IP adresinden giriş denemesi',
            risk_level='high'
        )
        
        send_security_alert_email(
            user=user,
            event_type='suspicious_activity',
            description='Hesabınıza farklı IP adreslerinden çoklu giriş denemeleri tespit edildi.',
            request=request
        )
        
        return True
    
    return False


def create_user_security_settings(user):
    """Kullanıcı için güvenlik ayarları oluştur"""
    settings_obj, created = UserSecuritySettings.objects.get_or_create(
        user=user,
        defaults={
            'two_factor_enabled': False,
            'login_notifications': True,
            'suspicious_activity_alerts': True,
        }
    )
    return settings_obj


def cleanup_expired_codes():
    """Süresi dolmuş doğrulama kodlarını temizle"""
    expired_count = EmailVerificationCode.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()[0]
    
    logger.info(f"Cleaned up {expired_count} expired verification codes")
    return expired_count


def cleanup_old_security_logs(days=90):
    """Eski güvenlik loglarını temizle (varsayılan 90 gün)"""
    cutoff_date = timezone.now() - timedelta(days=days)
    deleted_count = SecurityLog.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old security logs (older than {days} days)")
    return deleted_count