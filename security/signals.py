from django.db.models.signals import post_save, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.contrib.auth.hashers import make_password
from .models import SecurityLog, UserSecuritySettings
from .utils import (
    get_client_ip, get_user_agent, send_login_notification_email,
    detect_suspicious_activity, create_user_security_settings
)
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_security_settings_signal(sender, instance, created, **kwargs):
    """Yeni kullanıcı oluşturulduğunda güvenlik ayarları oluştur"""
    if created:
        create_user_security_settings(instance)
        
        # Kullanıcı kaydı logu
        SecurityLog.log_event(
            event_type='user_registered',
            user=instance,
            description=f'Yeni kullanıcı kaydı: {instance.username}',
            risk_level='low'
        )
        
        logger.info(f"Security settings created for new user: {instance.username}")


@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """Kullanıcı giriş yaptığında"""
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # Başarılı giriş logu
    SecurityLog.log_event(
        event_type='login_success',
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        description=f'Başarılı giriş: {user.username}',
        risk_level='low'
    )
    
    # Şüpheli aktivite kontrolü
    detect_suspicious_activity(user, request)
    
    # Giriş bildirimi gönder
    send_login_notification_email(user, request)
    
    logger.info(f"User logged in: {user.username} from {ip_address}")


@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """Kullanıcı çıkış yaptığında"""
    if user:  # user None olabilir
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Çıkış logu
        SecurityLog.log_event(
            event_type='logout',
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            description=f'Çıkış: {user.username}',
            risk_level='low'
        )
        
        logger.info(f"User logged out: {user.username} from {ip_address}")


@receiver(user_login_failed)
def user_login_failed_handler(sender, credentials, request, **kwargs):
    """Başarısız giriş denemesi"""
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    username = credentials.get('username', 'Bilinmiyor')
    
    # Kullanıcıyı bulmaya çalış
    user = None
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        try:
            # E-posta ile de deneyebilir
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            pass
    
    # Başarısız giriş logu
    SecurityLog.log_event(
        event_type='login_failed',
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        description=f'Başarısız giriş denemesi: {username}',
        risk_level='medium',
        username_attempted=username
    )
    
    logger.warning(f"Failed login attempt for: {username} from {ip_address}")


@receiver(pre_save, sender=User)
def user_password_change_handler(sender, instance, **kwargs):
    """Kullanıcı şifresi değiştirilmeden önce eski şifreyi kaydet"""
    if instance.pk:  # Mevcut kullanıcı güncelleniyor
        try:
            old_user = User.objects.get(pk=instance.pk)
            # Şifre değişti mi kontrol et
            if old_user.password != instance.password:
                # Eski şifreyi güvenlik ayarlarına ekle
                try:
                    settings = UserSecuritySettings.objects.get(user=instance)
                    settings.add_password_to_history(old_user.password)
                except UserSecuritySettings.DoesNotExist:
                    # Güvenlik ayarları yoksa oluştur
                    settings = create_user_security_settings(instance)
                    settings.add_password_to_history(old_user.password)
                
                # Şifre değişikliği logu
                SecurityLog.log_event(
                    event_type='password_change',
                    user=instance,
                    description=f'Şifre değiştirildi: {instance.username}',
                    risk_level='medium'
                )
                
                logger.info(f"Password changed for user: {instance.username}")
        except User.DoesNotExist:
            pass


# Custom signals for security events
from django.dispatch import Signal

# Özel güvenlik sinyalleri
two_factor_enabled = Signal()
two_factor_disabled = Signal()
two_factor_success = Signal()
two_factor_failed = Signal()
account_locked = Signal()
account_unlocked = Signal()
suspicious_activity_detected = Signal()


@receiver(two_factor_enabled)
def two_factor_enabled_handler(sender, user, request=None, **kwargs):
    """2FA etkinleştirildiğinde"""
    ip_address = get_client_ip(request) if request else None
    user_agent = get_user_agent(request) if request else ''
    
    SecurityLog.log_event(
        event_type='2fa_enabled',
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        description=f'İki faktörlü kimlik doğrulama etkinleştirildi: {user.username}',
        risk_level='low'
    )
    
    logger.info(f"2FA enabled for user: {user.username}")


@receiver(two_factor_disabled)
def two_factor_disabled_handler(sender, user, request=None, **kwargs):
    """2FA devre dışı bırakıldığında"""
    ip_address = get_client_ip(request) if request else None
    user_agent = get_user_agent(request) if request else ''
    
    SecurityLog.log_event(
        event_type='2fa_disabled',
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        description=f'İki faktörlü kimlik doğrulama devre dışı bırakıldı: {user.username}',
        risk_level='medium'
    )
    
    logger.warning(f"2FA disabled for user: {user.username}")


@receiver(two_factor_success)
def two_factor_success_handler(sender, user, request=None, **kwargs):
    """2FA başarılı olduğunda"""
    ip_address = get_client_ip(request) if request else None
    user_agent = get_user_agent(request) if request else ''
    
    SecurityLog.log_event(
        event_type='2fa_success',
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        description=f'İki faktörlü kimlik doğrulama başarılı: {user.username}',
        risk_level='low'
    )
    
    logger.info(f"2FA success for user: {user.username}")


@receiver(two_factor_failed)
def two_factor_failed_handler(sender, user, request=None, **kwargs):
    """2FA başarısız olduğunda"""
    ip_address = get_client_ip(request) if request else None
    user_agent = get_user_agent(request) if request else ''
    
    SecurityLog.log_event(
        event_type='2fa_failed',
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        description=f'İki faktörlü kimlik doğrulama başarısız: {user.username}',
        risk_level='high'
    )
    
    logger.warning(f"2FA failed for user: {user.username}")


@receiver(account_locked)
def account_locked_handler(sender, user, reason, request=None, **kwargs):
    """Hesap kilitlendiğinde"""
    ip_address = get_client_ip(request) if request else None
    
    SecurityLog.log_event(
        event_type='account_locked',
        user=user,
        ip_address=ip_address,
        description=f'Hesap kilitlendi: {reason}',
        risk_level='critical'
    )
    
    logger.critical(f"Account locked for user: {user.username}, reason: {reason}")


@receiver(account_unlocked)
def account_unlocked_handler(sender, user, request=None, **kwargs):
    """Hesap kilidi açıldığında"""
    ip_address = get_client_ip(request) if request else None
    
    SecurityLog.log_event(
        event_type='account_unlocked',
        user=user,
        ip_address=ip_address,
        description=f'Hesap kilidi açıldı: {user.username}',
        risk_level='medium'
    )
    
    logger.info(f"Account unlocked for user: {user.username}")


@receiver(suspicious_activity_detected)
def suspicious_activity_handler(sender, user, activity_type, request=None, **kwargs):
    """Şüpheli aktivite tespit edildiğinde"""
    ip_address = get_client_ip(request) if request else None
    
    SecurityLog.log_event(
        event_type='suspicious_activity',
        user=user,
        ip_address=ip_address,
        description=f'Şüpheli aktivite tespit edildi: {activity_type}',
        risk_level='high'
    )
    
    logger.warning(f"Suspicious activity detected for user: {user.username}, type: {activity_type}")