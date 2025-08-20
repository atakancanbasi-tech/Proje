from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
import random
import string
import hashlib
import json
import re
from datetime import datetime, timedelta
from .models import (
    UserSecuritySettings, 
    EmailVerificationCode, 
    SecurityLog, 
    AccountLockout,
    CaptchaChallenge,
    SuspiciousActivity,
    DeviceInfo,
    UserSession
)
from .forms import (
    SecureLoginForm,
    SecureRegistrationForm,
    SecuritySettingsForm,
    TwoFactorVerifyForm,
    PasswordResetRequestForm,
    ChangePasswordForm
)


def get_client_ip(request):
    """İstemci IP adresini al"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent_info(request):
    """Kullanıcı agent bilgisini al"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    return {
        'user_agent': user_agent[:500],
        'browser': 'Unknown',
        'operating_system': 'Unknown'
    }


def get_location_from_ip(ip_address):
    """IP adresinden konum bilgisi al"""
    return {
        'country': 'Unknown',
        'city': 'Unknown'
    }


def log_security_event(user, action, ip_address, user_agent, success=True, details=None):
    """Güvenlik olayını logla"""
    SecurityLog.objects.create(
        user=user,
        event_type=action,
        ip_address=ip_address,
        user_agent=user_agent,
        description=details or '',
        risk_level='low' if success else 'medium'
    )


def generate_verification_code():
    """6 haneli doğrulama kodu oluştur"""
    return ''.join(random.choices(string.digits, k=6))


def send_verification_email(user, code, request):
    """Doğrulama e-postası gönder"""
    context = {
        'user': user,
        'verification_code': code,
        'site_name': 'Satış Sitesi',
        'timestamp': timezone.now(),
        'ip_address': get_client_ip(request),
        'user_agent': get_user_agent_info(request)['user_agent']
    }
    
    html_message = render_to_string('security/emails/two_factor_code.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='İki Faktörlü Kimlik Doğrulama Kodu',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False
    )


def send_login_notification(user, request):
    """Giriş bildirimi e-postası gönder"""
    ip_address = get_client_ip(request)
    user_agent_info = get_user_agent_info(request)
    location = get_location_from_ip(ip_address)
    
    context = {
        'user': user,
        'timestamp': timezone.now(),
        'ip_address': ip_address,
        'location': location,
        'browser': user_agent_info['browser'],
        'operating_system': user_agent_info['operating_system'],
        'site_name': 'Satış Sitesi'
    }
    
    html_message = render_to_string('security/emails/login_notification.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='Hesabınıza Giriş Yapıldı',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True
    )


def send_security_alert(user, alert_type, details=None):
    """Güvenlik uyarısı gönder"""
    try:
        settings_obj = UserSecuritySettings.objects.get(user=user)
        if not settings_obj.suspicious_activity_alerts:
            return
    except UserSecuritySettings.DoesNotExist:
        return
    
    alert_messages = {
        'failed_login_attempts': {
            'subject': 'Güvenlik Uyarısı: Çoklu Başarısız Giriş Denemesi',
            'template': 'security/emails/failed_login_alert.html'
        },
        'account_locked': {
            'subject': 'Güvenlik Uyarısı: Hesabınız Kilitlendi',
            'template': 'security/emails/account_locked_alert.html'
        },
        'suspicious_activity': {
            'subject': 'Güvenlik Uyarısı: Şüpheli Aktivite Tespit Edildi',
            'template': 'security/emails/suspicious_activity_alert.html'
        },
        'password_changed': {
            'subject': 'Güvenlik Bildirimi: Şifreniz Değiştirildi',
            'template': 'security/emails/password_changed_alert.html'
        }
    }
    
    if alert_type not in alert_messages:
        return
    
    alert_info = alert_messages[alert_type]
    
    context = {
        'user': user,
        'alert_type': alert_type,
        'details': details or {},
        'timestamp': timezone.now()
    }
    
    try:
        html_message = render_to_string(alert_info['template'], context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=alert_info['subject'],
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True
        )
        
        # Güvenlik logu
        log_security_event(
            user=user,
            action='security_alert_sent',
            ip_address=details.get('ip_address') if details else None,
            user_agent=details.get('user_agent', '') if details else '',
            success=True,
            details=f'Alert type: {alert_type}'
        )
        
    except Exception as e:
        # Hata durumunda log kaydet
        log_security_event(
            user=user,
            action='security_alert_failed',
            ip_address=details.get('ip_address') if details else None,
            user_agent=details.get('user_agent', '') if details else '',
            success=False,
            details=f'Alert type: {alert_type}, Error: {str(e)}'
        )


def check_account_lockout(user):
    """Hesap kilidi kontrolü"""
    try:
        lockout = AccountLockout.objects.get(user=user)
        if lockout.is_locked():
            return True, lockout
    except AccountLockout.DoesNotExist:
        pass
    return False, None


def handle_failed_login(user, ip_address, user_agent):
    """Başarısız giriş denemesini işle"""
    lockout, created = AccountLockout.objects.get_or_create(
        user=user,
        defaults={
            'reason': 'failed_login',
            'failed_attempts': 0,
            'ip_address': ip_address
        }
    )
    
    lockout.failed_attempts += 1
    lockout.last_attempt_at = timezone.now()
    lockout.ip_address = ip_address
    
    # Progresif kilitleme süresi
    if lockout.failed_attempts >= 10:
        # 10+ deneme: 24 saat
        lockout.unlock_at = timezone.now() + timedelta(hours=24)
        lockout.description = f"Çok fazla başarısız giriş denemesi ({lockout.failed_attempts} deneme)"
    elif lockout.failed_attempts >= 7:
        # 7-9 deneme: 2 saat
        lockout.unlock_at = timezone.now() + timedelta(hours=2)
        lockout.description = f"Çoklu başarısız giriş denemesi ({lockout.failed_attempts} deneme)"
    elif lockout.failed_attempts >= 5:
        # 5-6 deneme: 30 dakika
        lockout.unlock_at = timezone.now() + timedelta(minutes=30)
        lockout.description = f"Başarısız giriş denemeleri ({lockout.failed_attempts} deneme)"
    
    lockout.save()
    
    # Güvenlik uyarısı gönder
    if lockout.failed_attempts >= 3:
        send_security_alert(user, 'failed_login_attempts', {
            'attempts': lockout.failed_attempts,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'timestamp': timezone.now().isoformat()
        })
    
    return lockout.failed_attempts >= 5


@csrf_protect
def secure_login(request):
    """Güvenli giriş view'ı"""
    if request.user.is_authenticated:
        return redirect('shop:product_list')
    
    if request.method == 'POST':
        form = SecureLoginForm(request.POST, request=request)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                messages.error(request, 'Geçersiz kullanıcı adı veya şifre.')
                return render(request, 'security/login.html', {'form': form})
            
            # Hesap kilidi kontrolü
            is_locked, lockout = check_account_lockout(user)
            if is_locked:
                messages.error(request, f'Hesabınız kilitli. Kilit açılma zamanı: {lockout.unlock_at}')
                return render(request, 'security/login.html', {'form': form})
            
            # Kimlik doğrulama
            user = authenticate(request, username=username, password=password)
            if user is not None:
                # 2FA kontrolü
                security_settings, created = UserSecuritySettings.objects.get_or_create(user=user)
                
                if security_settings.two_factor_enabled:
                    # 2FA kodu oluştur ve gönder
                    code = generate_verification_code()
                    verification_code = EmailVerificationCode.generate_code(
                        user=user,
                        code_type='2fa',
                        email=user.email,
                        ip_address=get_client_ip(request),
                        user_agent=get_user_agent_info(request)['user_agent']
                    )
                    verification_code.code = code
                    verification_code.save()
                    
                    send_verification_email(user, code, request)
                    
                    # Session'da kullanıcı bilgisini sakla
                    request.session['pre_2fa_user_id'] = user.id
                    request.session['2fa_required'] = True
                    
                    messages.info(request, 'E-posta adresinize gönderilen doğrulama kodunu girin.')
                    return redirect('security:two_factor_verify')
                else:
                    # Normal giriş
                    login(request, user)
                    
                    # Güvenlik logu
                    log_security_event(
                        user=user,
                        action='login_success',
                        ip_address=get_client_ip(request),
                        user_agent=get_user_agent_info(request)['user_agent'],
                        success=True
                    )
                    
                    # Giriş bildirimi gönder
                    if security_settings.login_notifications:
                        send_login_notification(user, request)
                    
                    messages.success(request, 'Başarıyla giriş yaptınız.')
                    return redirect('shop:product_list')
            else:
                # Başarısız giriş
                ip_address = get_client_ip(request)
                user_agent = get_user_agent_info(request)['user_agent']
                
                # Başarısız giriş logu
                log_security_event(
                    user=User.objects.get(username=username),
                    action='login_failed',
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                
                # Başarısız giriş sayacını artır
                is_locked = handle_failed_login(User.objects.get(username=username), ip_address, user_agent)
                
                if is_locked:
                    messages.error(request, 'Çok fazla başarısız giriş denemesi. Hesabınız 30 dakika kilitlendi.')
                else:
                    messages.error(request, 'Geçersiz kullanıcı adı veya şifre.')
    else:
        form = SecureLoginForm(request=request)
    
    return render(request, 'security/login.html', {'form': form})


@csrf_protect
def two_factor_verify(request):
    """İki faktörlü kimlik doğrulama view'ı"""
    if not request.session.get('2fa_required'):
        return redirect('security:login')
    
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('security:login')
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = TwoFactorVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            
            # Doğrulama kodunu kontrol et
            try:
                verification_code = EmailVerificationCode.objects.get(
                    user=user,
                    code=code,
                    code_type='2fa',
                    is_used=False
                )
                
                if verification_code.is_valid():
                    # Kodu kullanılmış olarak işaretle
                    verification_code.mark_as_used()
                    
                    # Kullanıcıyı giriş yap
                    login(request, user)
                    
                    # Session temizle
                    del request.session['2fa_required']
                    del request.session['pre_2fa_user_id']
                    
                    # Güvenlik logu
                    log_security_event(
                        user=user,
                        action='2fa_success',
                        ip_address=get_client_ip(request),
                        user_agent=get_user_agent_info(request)['user_agent'],
                        success=True
                    )
                    
                    # Giriş bildirimi gönder
                    security_settings = UserSecuritySettings.objects.get(user=user)
                    if security_settings.login_notifications:
                        send_login_notification(user, request)
                    
                    messages.success(request, 'İki faktörlü kimlik doğrulama başarılı.')
                    return redirect('shop:product_list')
                else:
                    messages.error(request, 'Doğrulama kodunun süresi dolmuş.')
            except EmailVerificationCode.DoesNotExist:
                messages.error(request, 'Geçersiz doğrulama kodu.')
                
                # Başarısız 2FA logu
                log_security_event(
                    user=user,
                    action='2fa_failed',
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent_info(request)['user_agent'],
                    success=False
                )
    else:
        form = TwoFactorVerifyForm()
    
    return render(request, 'security/two_factor_verify.html', {'form': form})


@require_http_methods(["POST"])
def resend_verification_code(request):
    """Doğrulama kodunu yeniden gönder"""
    if not request.session.get('2fa_required'):
        return JsonResponse({'success': False, 'message': 'Geçersiz istek.'})
    
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'Kullanıcı bulunamadı.'})
    
    user = get_object_or_404(User, id=user_id)
    
    # Yeni kod oluştur
    code = generate_verification_code()
    verification_code = EmailVerificationCode.generate_code(
        user=user,
        code_type='2fa',
        email=user.email,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent_info(request)['user_agent']
    )
    verification_code.code = code
    verification_code.save()
    
    send_verification_email(user, code, request)
    
    return JsonResponse({'success': True, 'message': 'Doğrulama kodu yeniden gönderildi.'})


def secure_logout(request):
    """Güvenli çıkış view'ı"""
    if request.user.is_authenticated:
        # Güvenlik logu
        log_security_event(
            user=request.user,
            action='logout',
            ip_address=get_client_ip(request),
            user_agent=get_user_agent_info(request)['user_agent'],
            success=True
        )
        
        logout(request)
        messages.success(request, 'Başarıyla çıkış yaptınız.')
    
    return redirect('shop:product_list')


@csrf_protect
def secure_register(request):
    """Güvenli kayıt view'ı"""
    if request.method == 'POST':
        form = SecureRegistrationForm(request.POST, request=request)
        if form.is_valid():
            user = form.save()
            
            # Güvenlik logu
            log_security_event(
                user=user,
                action='registration',
                ip_address=get_client_ip(request),
                user_agent=get_user_agent_info(request)['user_agent'],
                success=True
            )
            
            messages.success(request, 'Hesabınız başarıyla oluşturuldu. Giriş yapabilirsiniz.')
            return redirect('security:login')
    else:
        form = SecureRegistrationForm(request=request)
    
    return render(request, 'security/register.html', {'form': form})


@login_required
@csrf_protect
def security_settings(request):
    """Güvenlik ayarları view'ı"""
    security_settings, created = UserSecuritySettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = SecuritySettingsForm(request.POST, instance=security_settings)
        if form.is_valid():
            form.save()
            
            # Güvenlik logu
            log_security_event(
                user=request.user,
                action='security_settings_updated',
                ip_address=get_client_ip(request),
                user_agent=get_user_agent_info(request)['user_agent'],
                success=True
            )
            
            messages.success(request, 'Güvenlik ayarlarınız güncellendi.')
            return redirect('security:security_settings')
    else:
        form = SecuritySettingsForm(instance=security_settings)
    
    context = {
        'form': form,
        'security_settings': security_settings
    }
    
    return render(request, 'security/security_settings.html', context)


@login_required
@csrf_protect
def change_password(request):
    """Şifre değiştirme view'ı"""
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST, user=request.user)
        if form.is_valid():
            # Eski şifreyi kaydet
            old_password_hash = request.user.password
            
            user = form.save()
            update_session_auth_hash(request, user)
            
            # Şifre geçmişini güncelle
            try:
                settings_obj, created = UserSecuritySettings.objects.get_or_create(user=request.user)
                
                # Mevcut şifre geçmişini al
                password_history = settings_obj.password_history or []
                
                # Eski şifreyi geçmişe ekle
                password_history.append(old_password_hash)
                
                # Son 5 şifreyi tut
                if len(password_history) > 5:
                    password_history = password_history[-5:]
                
                settings_obj.password_history = password_history
                settings_obj.save()
                
            except Exception as e:
                # Hata durumunda log kaydet ama işlemi durdurma
                log_security_event(
                    user=request.user,
                    action='password_history_update_failed',
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent_info(request)['user_agent'],
                    success=False,
                    details=f'Error: {str(e)}'
                )
            
            # Güvenlik logu
            log_security_event(
                user=request.user,
                action='password_changed',
                ip_address=get_client_ip(request),
                user_agent=get_user_agent_info(request)['user_agent'],
                success=True
            )
            
            # Şifre değişikliği bildirimi gönder
            try:
                send_security_alert(
                    user=request.user,
                    alert_type='password_changed',
                    details={
                        'ip_address': get_client_ip(request),
                        'user_agent': get_user_agent_info(request)['user_agent'],
                        'location': get_location_from_ip(get_client_ip(request))['city']
                    }
                )
            except Exception as e:
                # E-posta gönderimi başarısız olsa bile işlemi durdurma
                log_security_event(
                    user=request.user,
                    action='password_change_notification_failed',
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent_info(request)['user_agent'],
                    success=False,
                    details=f'Email notification error: {str(e)}'
                )
            
            messages.success(request, 'Şifreniz başarıyla değiştirildi.')
            return redirect('security:security_settings')
    else:
        form = ChangePasswordForm(user=request.user)
    
    return render(request, 'security/change_password.html', {'form': form})


@login_required
def security_logs(request):
    """Güvenlik logları view'ı"""
    # Filtreleme
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    ip_filter = request.GET.get('ip', '')
    
    logs = SecurityLog.objects.filter(user=request.user).order_by('-created_at')
    
    if action_filter:
        logs = logs.filter(event_type=action_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if ip_filter:
        logs = logs.filter(ip_address__icontains=ip_filter)
    
    # Sayfalama
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # İstatistikler
    stats = {
        'total_logs': logs.count(),
        'successful_logins': logs.filter(event_type='login_success').count(),
        'failed_logins': logs.filter(event_type='login_failed').count(),
        'password_changes': logs.filter(event_type='password_changed').count(),
    }
    
    # Eylem türleri
    action_choices = [
        ('login_success', 'Başarılı Giriş'),
        ('login_failed', 'Başarısız Giriş'),
        ('2fa_success', '2FA Başarılı'),
        ('2fa_failed', '2FA Başarısız'),
        ('logout', 'Çıkış'),
        ('password_changed', 'Şifre Değiştirildi'),
        ('registration', 'Kayıt'),
        ('security_settings_updated', 'Güvenlik Ayarları Güncellendi'),
    ]
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'action_choices': action_choices,
        'current_filters': {
            'action': action_filter,
            'date_from': date_from,
            'date_to': date_to,
            'ip': ip_filter,
        }
    }
    
    return render(request, 'security/security_logs.html', context)


@csrf_protect
def password_reset_request(request):
    """Şifre sıfırlama isteği view'ı"""
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Token oluştur
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # E-posta gönder
                reset_url = request.build_absolute_uri(
                    reverse('security:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                )
                
                context = {
                    'user': user,
                    'reset_url': reset_url,
                    'site_name': 'Satış Sitesi'
                }
                
                html_message = render_to_string('security/emails/password_reset.html', context)
                plain_message = strip_tags(html_message)
                
                send_mail(
                    subject='Şifre Sıfırlama',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False
                )
                
                # Güvenlik logu
                log_security_event(
                    user=user,
                    action='password_reset_request',
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent_info(request)['user_agent'],
                    success=True
                )
                
                messages.success(request, 'Şifre sıfırlama bağlantısı e-posta adresinize gönderildi.')
                return redirect('security:login')
                
            except User.DoesNotExist:
                messages.error(request, 'Bu e-posta adresi ile kayıtlı kullanıcı bulunamadı.')
    else:
        form = PasswordResetRequestForm()
    
    return render(request, 'security/password_reset_request.html', {'form': form})


@csrf_protect
def password_reset_confirm(request, uidb64, token):
    """Şifre sıfırlama onaylama view'ı"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            if password1 and password2:
                if password1 == password2:
                    try:
                        # Django'nun varsayılan şifre doğrulaması
                        validate_password(password1, user)
                        
                        # Ek güvenlik kontrolleri
                        if len(password1) < 12:
                            raise ValidationError('Şifre en az 12 karakter olmalıdır.')
                        
                        # Karmaşıklık kontrolleri
                        if not re.search(r'[A-Z]', password1):
                            raise ValidationError('Şifre en az bir büyük harf içermelidir.')
                        
                        if not re.search(r'[a-z]', password1):
                            raise ValidationError('Şifre en az bir küçük harf içermelidir.')
                        
                        if not re.search(r'\d', password1):
                            raise ValidationError('Şifre en az bir rakam içermelidir.')
                        
                        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password1):
                            raise ValidationError('Şifre en az bir özel karakter içermelidir.')
                        
                        # Yaygın şifreler kontrolü
                        common_passwords = [
                            'password', '123456', '123456789', 'qwerty', 'abc123',
                            'password123', 'admin', 'letmein', 'welcome', 'monkey'
                        ]
                        if password1.lower() in common_passwords:
                            raise ValidationError('Bu şifre çok yaygın kullanılıyor. Lütfen daha güvenli bir şifre seçin.')
                        
                        # Şifre geçmişi kontrolü
                        try:
                            from django.contrib.auth.hashers import check_password
                            settings_obj = UserSecuritySettings.objects.get(user=user)
                            
                            for old_hash in (settings_obj.password_history or []):
                                if check_password(password1, old_hash):
                                    raise ValidationError('Bu şifreyi daha önce kullandınız. Lütfen farklı bir şifre seçin.')
                        except UserSecuritySettings.DoesNotExist:
                            pass
                        
                        # Eski şifreyi kaydet
                        old_password_hash = user.password
                        
                        user.set_password(password1)
                        user.save()
                        
                        # Şifre geçmişini güncelle
                        try:
                            settings_obj, created = UserSecuritySettings.objects.get_or_create(user=user)
                            
                            # Mevcut şifre geçmişini al
                            password_history = settings_obj.password_history or []
                            
                            # Eski şifreyi geçmişe ekle
                            if old_password_hash:  # İlk şifre değişikliği değilse
                                password_history.append(old_password_hash)
                            
                            # Son 5 şifreyi tut
                            if len(password_history) > 5:
                                password_history = password_history[-5:]
                            
                            settings_obj.password_history = password_history
                            settings_obj.save()
                            
                        except Exception as e:
                            # Hata durumunda log kaydet ama işlemi durdurma
                            log_security_event(
                                user=user,
                                action='password_history_update_failed',
                                ip_address=get_client_ip(request),
                                user_agent=get_user_agent_info(request)['user_agent'],
                                success=False,
                                details=f'Error: {str(e)}'
                            )
                        
                        # Güvenlik logu
                        log_security_event(
                            user=user,
                            action='password_reset_success',
                            ip_address=get_client_ip(request),
                            user_agent=get_user_agent_info(request)['user_agent'],
                            success=True
                        )
                        
                        messages.success(request, 'Şifreniz başarıyla sıfırlandı. Yeni şifrenizle giriş yapabilirsiniz.')
                        return redirect('security:login')
                    except ValidationError as e:
                        if hasattr(e, 'messages'):
                            for error in e.messages:
                                messages.error(request, error)
                        else:
                            messages.error(request, str(e))
                else:
                    messages.error(request, 'Şifreler eşleşmiyor.')
            else:
                messages.error(request, 'Lütfen tüm alanları doldurun.')
        
        return render(request, 'security/password_reset_confirm.html', {'validlink': True})
    else:
        return render(request, 'security/password_reset_confirm.html', {'validlink': False})


def generate_captcha_image(request):
    """CAPTCHA görüntüsü oluştur (SVG formatında)"""
    from django.http import HttpResponse
    
    # Session key'i al veya oluştur
    if not request.session.session_key:
        request.session.create()
    
    session_key = request.session.session_key
    ip_address = get_client_ip(request)
    
    # Yeni CAPTCHA oluştur
    captcha = CaptchaChallenge.generate_math_challenge(session_key, ip_address)
    
    # SVG CAPTCHA oluştur
    svg_content = f'''
    <svg width="200" height="60" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <pattern id="noise" patternUnits="userSpaceOnUse" width="4" height="4">
                <rect width="4" height="4" fill="#f8f9fa"/>
                <circle cx="2" cy="2" r="0.5" fill="#dee2e6"/>
            </pattern>
        </defs>
        <rect width="200" height="60" fill="url(#noise)"/>
        <text x="100" y="35" font-family="Arial, sans-serif" font-size="24" font-weight="bold" 
              text-anchor="middle" fill="#495057" transform="rotate({random.randint(-5, 5)} 100 35)">
            {captcha.question}
        </text>
        <line x1="{random.randint(10, 50)}" y1="{random.randint(10, 50)}" 
              x2="{random.randint(150, 190)}" y2="{random.randint(10, 50)}" 
              stroke="#6c757d" stroke-width="1" opacity="0.3"/>
        <line x1="{random.randint(10, 50)}" y1="{random.randint(10, 50)}" 
              x2="{random.randint(150, 190)}" y2="{random.randint(10, 50)}" 
              stroke="#6c757d" stroke-width="1" opacity="0.3"/>
    </svg>
    '''
    
    return HttpResponse(svg_content, content_type='image/svg+xml')


@require_http_methods(["POST"])
def refresh_captcha(request):
    """CAPTCHA yenileme"""
    # Session key'i al veya oluştur
    if not request.session.session_key:
        request.session.create()
    
    session_key = request.session.session_key
    ip_address = get_client_ip(request)
    
    # Yeni CAPTCHA oluştur
    captcha = CaptchaChallenge.generate_math_challenge(session_key, ip_address)
    
    return JsonResponse({
        'success': True,
        'captcha_url': f'/security/captcha/image/?t={timezone.now().timestamp()}'
    })


@require_http_methods(["POST"])
def cleanup_expired_captcha(request):
    """Süresi dolmuş CAPTCHA'ları temizle (admin işlemi)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    cleaned_count = CaptchaChallenge.cleanup_expired()
    
    return JsonResponse({
        'success': True,
        'cleaned_count': cleaned_count,
        'message': f'{cleaned_count} adet süresi dolmuş CAPTCHA temizlendi.'
    })


@login_required
def suspicious_activities(request):
    """Şüpheli aktiviteleri listele"""
    # Sadece admin kullanıcılar erişebilir
    if not request.user.is_staff:
        messages.error(request, 'Bu sayfaya erişim yetkiniz yok.')
        return redirect('security:security_settings')
    
    # Filtreleme parametreleri
    activity_type = request.GET.get('activity_type', '')
    severity = request.GET.get('severity', '')
    status = request.GET.get('status', '')
    user_filter = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Temel sorgu
    activities = SuspiciousActivity.objects.all()
    
    # Filtreleri uygula
    if activity_type:
        activities = activities.filter(activity_type=activity_type)
    
    if severity:
        activities = activities.filter(severity=severity)
    
    if status:
        activities = activities.filter(status=status)
    
    if user_filter:
        activities = activities.filter(
            Q(user__username__icontains=user_filter) |
            Q(user__email__icontains=user_filter)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            activities = activities.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            activities = activities.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    # Sayfalama
    paginator = Paginator(activities, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # İstatistikler
    stats = {
        'total': SuspiciousActivity.objects.count(),
        'pending': SuspiciousActivity.objects.filter(status='detected').count(),
        'high_risk': SuspiciousActivity.objects.filter(severity__in=['high', 'critical']).count(),
        'today': SuspiciousActivity.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'activity_types': SuspiciousActivity.ACTIVITY_TYPES,
        'severity_levels': SuspiciousActivity.SEVERITY_LEVELS,
        'status_choices': SuspiciousActivity.STATUS_CHOICES,
        'filters': {
            'activity_type': activity_type,
            'severity': severity,
            'status': status,
            'user': user_filter,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'security/suspicious_activities.html', context)


@login_required
@require_http_methods(["POST"])
def update_suspicious_activity(request, activity_id):
    """Şüpheli aktivite durumunu güncelle"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Yetkiniz yok'})
    
    try:
        activity = get_object_or_404(SuspiciousActivity, id=activity_id)
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'resolve':
            activity.mark_as_resolved(notes)
            message = 'Şüpheli aktivite çözüldü olarak işaretlendi'
        elif action == 'confirm':
            activity.status = 'confirmed'
            if notes:
                activity.notes = notes
            activity.save()
            message = 'Şüpheli aktivite doğrulandı'
        elif action == 'false_positive':
            activity.status = 'false_positive'
            if notes:
                activity.notes = notes
            activity.save()
            message = 'Yanlış pozitif olarak işaretlendi'
        elif action == 'investigate':
            activity.status = 'investigating'
            if notes:
                activity.notes = notes
            activity.save()
            message = 'İnceleme durumuna alındı'
        else:
            return JsonResponse({'success': False, 'error': 'Geçersiz işlem'})
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='suspicious_activity_updated',
            user=request.user,
            ip_address=get_client_ip(request),
            description=f'Şüpheli aktivite #{activity_id} güncellendi: {action}',
            risk_level='low',
            suspicious_activity_id=activity_id
        )
        
        return JsonResponse({
            'success': True,
            'message': message,
            'new_status': activity.get_status_display()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Hata oluştu: {str(e)}'
        })


@login_required
def suspicious_activity_detail(request, activity_id):
    """Şüpheli aktivite detayları"""
    if not request.user.is_staff:
        messages.error(request, 'Bu sayfaya erişim yetkiniz yok.')
        return redirect('security:security_settings')
    
    activity = get_object_or_404(SuspiciousActivity, id=activity_id)
    
    # İlgili güvenlik logları
    related_logs = SecurityLog.objects.filter(
        Q(suspicious_activity_id=activity_id) |
        Q(ip_address=activity.ip_address, created_at__date=activity.created_at.date())
    ).order_by('-created_at')[:20]
    
    # Aynı IP'den diğer şüpheli aktiviteler
    related_activities = SuspiciousActivity.objects.filter(
        ip_address=activity.ip_address
    ).exclude(id=activity_id).order_by('-created_at')[:10]
    
    # Kullanıcının diğer şüpheli aktiviteleri
    user_activities = []
    if activity.user:
        user_activities = SuspiciousActivity.objects.filter(
            user=activity.user
        ).exclude(id=activity_id).order_by('-created_at')[:10]
    
    context = {
        'activity': activity,
        'related_logs': related_logs,
        'related_activities': related_activities,
        'user_activities': user_activities,
    }
    
    return render(request, 'security/suspicious_activity_detail.html', context)


@login_required
def security_dashboard(request):
    """Güvenlik dashboard'u"""
    if not request.user.is_staff:
        messages.error(request, 'Bu sayfaya erişim yetkiniz yok.')
        return redirect('security:security_settings')
    
    # Son 24 saat istatistikleri
    last_24h = timezone.now() - timedelta(hours=24)
    
    stats = {
        'suspicious_activities_24h': SuspiciousActivity.objects.filter(
            created_at__gte=last_24h
        ).count(),
        'failed_logins_24h': SecurityLog.objects.filter(
            event_type='login_failed',
            created_at__gte=last_24h
        ).count(),
        'successful_logins_24h': SecurityLog.objects.filter(
            event_type='login_success',
            created_at__gte=last_24h
        ).count(),
        'locked_accounts': AccountLockout.objects.filter(
            is_locked=True
        ).count(),
        'high_risk_activities': SuspiciousActivity.objects.filter(
            severity__in=['high', 'critical'],
            status__in=['detected', 'investigating']
        ).count(),
    }
    
    # Son şüpheli aktiviteler
    recent_activities = SuspiciousActivity.objects.filter(
        severity__in=['medium', 'high', 'critical']
    ).order_by('-created_at')[:10]
    
    # En çok şüpheli aktivite olan IP'ler
    top_ips = SuspiciousActivity.objects.values('ip_address').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Aktivite türü dağılımı
    activity_distribution = SuspiciousActivity.objects.values('activity_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'stats': stats,
        'recent_activities': recent_activities,
        'top_ips': top_ips,
        'activity_distribution': activity_distribution,
    }
    
    return render(request, 'security/security_dashboard.html', context)


def detect_and_handle_suspicious_activity(request, user=None, activity_type=None):
    """Şüpheli aktivite tespit et ve işle"""
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Konum bilgisi al
    location_data = get_location_from_ip(ip_address)
    
    # Cihaz parmak izi oluştur
    device_fingerprint = hashlib.md5(
        f"{user_agent}{request.META.get('HTTP_ACCEPT_LANGUAGE', '')}".encode()
    ).hexdigest()
    
    activities_detected = []
    
    # Çoklu başarısız giriş tespiti
    if activity_type == 'login_failed':
        activity = SuspiciousActivity.detect_suspicious_login_attempts(ip_address)
        if activity:
            activities_detected.append(activity)
    
    # Olağandışı konum tespiti
    if user and activity_type == 'login_success':
        activity = SuspiciousActivity.detect_unusual_location(user, ip_address, location_data)
        if activity:
            activities_detected.append(activity)
    
    # Hızlı istekler tespiti
    activity = SuspiciousActivity.detect_rapid_requests(ip_address)
    if activity:
        activities_detected.append(activity)
    
    # Tespit edilen aktiviteler için bildirimler gönder
    for activity in activities_detected:
        activity.notify_admin()
        if activity.user:
            activity.notify_user()
    
    return activities_detected


# Oturum ve Cihaz Yönetimi View'ları

def get_device_fingerprint(request):
    """Cihaz parmak izi oluştur"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
    
    # Basit bir fingerprint oluştur
    fingerprint_data = f"{user_agent}|{accept_language}|{accept_encoding}"
    return hashlib.md5(fingerprint_data.encode()).hexdigest()


def parse_user_agent(user_agent):
    """User agent'tan cihaz bilgilerini çıkar"""
    device_info = {
        'browser_name': 'Unknown',
        'browser_version': '',
        'os_name': 'Unknown',
        'os_version': '',
        'device_type': 'unknown'
    }
    
    if not user_agent:
        return device_info
    
    # Tarayıcı tespiti
    if 'Chrome' in user_agent:
        device_info['browser_name'] = 'Chrome'
        match = re.search(r'Chrome/([\d.]+)', user_agent)
        if match:
            device_info['browser_version'] = match.group(1)
    elif 'Firefox' in user_agent:
        device_info['browser_name'] = 'Firefox'
        match = re.search(r'Firefox/([\d.]+)', user_agent)
        if match:
            device_info['browser_version'] = match.group(1)
    elif 'Safari' in user_agent and 'Chrome' not in user_agent:
        device_info['browser_name'] = 'Safari'
        match = re.search(r'Version/([\d.]+)', user_agent)
        if match:
            device_info['browser_version'] = match.group(1)
    elif 'Edge' in user_agent:
        device_info['browser_name'] = 'Edge'
        match = re.search(r'Edge/([\d.]+)', user_agent)
        if match:
            device_info['browser_version'] = match.group(1)
    
    # İşletim sistemi tespiti
    if 'Windows' in user_agent:
        device_info['os_name'] = 'Windows'
        if 'Windows NT 10.0' in user_agent:
            device_info['os_version'] = '10'
        elif 'Windows NT 6.3' in user_agent:
            device_info['os_version'] = '8.1'
        elif 'Windows NT 6.1' in user_agent:
            device_info['os_version'] = '7'
    elif 'Mac OS X' in user_agent:
        device_info['os_name'] = 'macOS'
        match = re.search(r'Mac OS X ([\d_]+)', user_agent)
        if match:
            device_info['os_version'] = match.group(1).replace('_', '.')
    elif 'Linux' in user_agent:
        device_info['os_name'] = 'Linux'
    elif 'Android' in user_agent:
        device_info['os_name'] = 'Android'
        match = re.search(r'Android ([\d.]+)', user_agent)
        if match:
            device_info['os_version'] = match.group(1)
    elif 'iOS' in user_agent or 'iPhone' in user_agent or 'iPad' in user_agent:
        device_info['os_name'] = 'iOS'
        match = re.search(r'OS ([\d_]+)', user_agent)
        if match:
            device_info['os_version'] = match.group(1).replace('_', '.')
    
    # Cihaz türü tespiti
    if 'Mobile' in user_agent or 'Android' in user_agent or 'iPhone' in user_agent:
        device_info['device_type'] = 'mobile'
    elif 'iPad' in user_agent or 'Tablet' in user_agent:
        device_info['device_type'] = 'tablet'
    else:
        device_info['device_type'] = 'desktop'
    
    return device_info


def create_user_session(request, user):
    """Kullanıcı oturumu oluştur"""
    device_fingerprint = get_device_fingerprint(request)
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    location_data = get_location_from_ip(ip_address)
    
    # Cihaz bilgilerini al veya oluştur
    device_data = parse_user_agent(user_agent)
    device, created = DeviceInfo.get_or_create_device(
        user=user,
        device_fingerprint=device_fingerprint,
        device_data=device_data
    )
    
    # Cihaz aktivitesini güncelle
    device.update_activity(ip_address, location_data)
    
    # Oturum oluştur
    session = UserSession.create_session(
        user=user,
        session_key=request.session.session_key,
        device_fingerprint=device_fingerprint,
        ip_address=ip_address,
        user_agent=user_agent,
        location_data=location_data
    )
    
    return session, device


@login_required
def session_management(request):
    """Oturum yönetimi sayfası"""
    user = request.user
    
    # Aktif oturumları al
    active_sessions = UserSession.get_active_sessions(user)
    
    # Kullanıcının cihazlarını al
    devices = DeviceInfo.objects.filter(user=user).order_by('-last_seen')
    
    # İstatistikler
    stats = {
        'total_sessions': active_sessions.count(),
        'total_devices': devices.count(),
        'trusted_devices': devices.filter(trust_level='trusted').count(),
        'suspicious_devices': devices.filter(trust_level='suspicious').count(),
        'blocked_devices': devices.filter(trust_level='blocked').count(),
    }
    
    # Mevcut oturum bilgisi
    current_session = None
    try:
        current_session = UserSession.objects.get(
            session_key=request.session.session_key,
            is_active=True
        )
    except UserSession.DoesNotExist:
        pass
    
    context = {
        'active_sessions': active_sessions,
        'devices': devices,
        'stats': stats,
        'current_session': current_session,
    }
    
    return render(request, 'security/session_management.html', context)


@login_required
@require_http_methods(["POST"])
def end_session(request, session_id):
    """Belirli bir oturumu sonlandır"""
    try:
        session = get_object_or_404(
            UserSession,
            id=session_id,
            user=request.user,
            is_active=True
        )
        
        # Mevcut oturumu sonlandırmaya çalışıyorsa engelle
        if session.session_key == request.session.session_key:
            return JsonResponse({
                'success': False,
                'error': 'Mevcut oturumunuzu sonlandıramazsınız'
            })
        
        session.end_session('user_action')
        
        return JsonResponse({
            'success': True,
            'message': 'Oturum başarıyla sonlandırıldı'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def end_all_sessions(request):
    """Tüm oturumları sonlandır (mevcut hariç)"""
    try:
        UserSession.end_all_sessions(
            user=request.user,
            except_session=request.session.session_key,
            reason='user_security_action'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Tüm diğer oturumlar sonlandırıldı'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def trust_device(request, device_id):
    """Cihazı güvenilir olarak işaretle"""
    try:
        device = get_object_or_404(
            DeviceInfo,
            id=device_id,
            user=request.user
        )
        
        device.mark_as_trusted()
        
        return JsonResponse({
            'success': True,
            'message': 'Cihaz güvenilir olarak işaretlendi'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def block_device(request, device_id):
    """Cihazı engelle"""
    try:
        device = get_object_or_404(
            DeviceInfo,
            id=device_id,
            user=request.user
        )
        
        # Mevcut cihazı engellemeye çalışıyorsa uyar
        current_fingerprint = get_device_fingerprint(request)
        if device.device_fingerprint == current_fingerprint:
            return JsonResponse({
                'success': False,
                'error': 'Mevcut cihazınızı engelleyemezsiniz'
            })
        
        reason = request.POST.get('reason', 'Kullanıcı tarafından engellendi')
        device.block_device(reason)
        
        return JsonResponse({
            'success': True,
            'message': 'Cihaz başarıyla engellendi'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def rename_device(request, device_id):
    """Cihaz adını değiştir"""
    try:
        device = get_object_or_404(
            DeviceInfo,
            id=device_id,
            user=request.user
        )
        
        new_name = request.POST.get('name', '').strip()
        if not new_name:
            return JsonResponse({
                'success': False,
                'error': 'Cihaz adı boş olamaz'
            })
        
        if len(new_name) > 200:
            return JsonResponse({
                'success': False,
                'error': 'Cihaz adı çok uzun'
            })
        
        device.device_name = new_name
        device.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Cihaz adı güncellendi'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def device_detail(request, device_id):
    """Cihaz detay sayfası"""
    device = get_object_or_404(
        DeviceInfo,
        id=device_id,
        user=request.user
    )
    
    # Cihazın oturum geçmişi
    sessions = UserSession.objects.filter(
        user=request.user,
        device_fingerprint=device.device_fingerprint
    ).order_by('-created_at')[:20]
    
    # Cihazla ilgili güvenlik logları
    security_logs = SecurityLog.objects.filter(
        user=request.user,
        device_fingerprint=device.device_fingerprint
    ).order_by('-created_at')[:50]
    
    context = {
        'device': device,
        'sessions': sessions,
        'security_logs': security_logs,
    }
    
    return render(request, 'security/device_detail.html', context)


@login_required
def session_detail(request, session_id):
    """Oturum detay sayfası"""
    session = get_object_or_404(
        UserSession,
        id=session_id,
        user=request.user
    )
    
    # Oturumla ilgili güvenlik logları
    security_logs = SecurityLog.objects.filter(
        user=request.user,
        session_id=session.session_key
    ).order_by('-created_at')[:50]
    
    # Cihaz bilgisi
    device = None
    try:
        device = DeviceInfo.objects.get(
            user=request.user,
            device_fingerprint=session.device_fingerprint
        )
    except DeviceInfo.DoesNotExist:
        pass
    
    context = {
        'session': session,
        'device': device,
        'security_logs': security_logs,
    }
    
    return render(request, 'security/session_detail.html', context)