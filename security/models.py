from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import secrets
import string


class EmailVerificationCode(models.Model):
    """E-posta doğrulama kodları için model"""
    CODE_TYPES = [
        ('2fa', 'İki Faktörlü Kimlik Doğrulama'),
        ('password_reset', 'Şifre Sıfırlama'),
        ('email_change', 'E-posta Değişikliği'),
        ('account_verification', 'Hesap Doğrulama'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_codes')
    code = models.CharField(max_length=6)
    code_type = models.CharField(max_length=20, choices=CODE_TYPES)
    email = models.EmailField()  # Hangi e-posta adresine gönderildiği
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'E-posta Doğrulama Kodu'
        verbose_name_plural = 'E-posta Doğrulama Kodları'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_code_type_display()} - {self.code}"
    
    @classmethod
    def generate_code(cls, user, code_type, email=None, ip_address=None, user_agent='', expires_minutes=10):
        """Yeni doğrulama kodu oluştur"""
        # Eski kodları temizle
        cls.objects.filter(
            user=user,
            code_type=code_type,
            is_used=False,
            expires_at__lt=timezone.now()
        ).delete()
        
        # Yeni kod oluştur
        code = ''.join(secrets.choice(string.digits) for _ in range(6))
        expires_at = timezone.now() + timedelta(minutes=expires_minutes)
        
        return cls.objects.create(
            user=user,
            code=code,
            code_type=code_type,
            email=email or user.email,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def is_valid(self):
        """Kodun geçerli olup olmadığını kontrol et"""
        return not self.is_used and self.expires_at > timezone.now()
    
    def mark_as_used(self):
        """Kodu kullanılmış olarak işaretle"""
        self.is_used = True
        self.save()


class SecurityLog(models.Model):
    """Güvenlik olayları için log modeli"""
    EVENT_TYPES = [
        ('login_success', 'Başarılı Giriş'),
        ('login_failed', 'Başarısız Giriş'),
        ('logout', 'Çıkış'),
        ('password_change', 'Şifre Değişikliği'),
        ('email_change', 'E-posta Değişikliği'),
        ('2fa_enabled', '2FA Etkinleştirildi'),
        ('2fa_disabled', '2FA Devre Dışı Bırakıldı'),
        ('2fa_success', '2FA Başarılı'),
        ('2fa_failed', '2FA Başarısız'),
        ('account_locked', 'Hesap Kilitlendi'),
        ('account_unlocked', 'Hesap Kilidi Açıldı'),
        ('suspicious_activity', 'Şüpheli Aktivite'),
        ('password_reset_request', 'Şifre Sıfırlama İsteği'),
        ('password_reset_success', 'Şifre Sıfırlama Başarılı'),
        ('session_created', 'Oturum Oluşturuldu'),
        ('session_ended', 'Oturum Sonlandırıldı'),
        ('session_suspicious', 'Şüpheli Oturum'),
        ('all_sessions_ended', 'Tüm Oturumlar Sonlandırıldı'),
        ('new_device_detected', 'Yeni Cihaz Tespit Edildi'),
        ('device_trusted', 'Cihaz Güvenilir İşaretlendi'),
        ('device_suspicious', 'Cihaz Şüpheli İşaretlendi'),
        ('device_blocked', 'Cihaz Engellendi'),
    ]
    
    RISK_LEVELS = [
        ('low', 'Düşük'),
        ('medium', 'Orta'),
        ('high', 'Yüksek'),
        ('critical', 'Kritik'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_logs', null=True, blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='low')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    description = models.TextField(blank=True)
    additional_data = models.JSONField(default=dict, blank=True)
    suspicious_activity_id = models.PositiveIntegerField(null=True, blank=True)  # SuspiciousActivity ile ilişki
    location_data = models.JSONField(default=dict, blank=True)  # Konum bilgileri
    device_fingerprint = models.CharField(max_length=255, blank=True)  # Cihaz parmak izi
    session_id = models.CharField(max_length=255, blank=True)  # Oturum ID'si
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Güvenlik Logu'
        verbose_name_plural = 'Güvenlik Logları'
    
    def __str__(self):
        username = self.user.username if self.user else 'Anonim'
        return f"{username} - {self.get_event_type_display()} - {self.created_at}"
    
    @classmethod
    def log_event(cls, event_type, user=None, ip_address=None, user_agent='', description='', risk_level='low', 
                  suspicious_activity_id=None, location_data=None, device_fingerprint='', session_id='', **additional_data):
        """Güvenlik olayını logla"""
        log_entry = cls.objects.create(
            user=user,
            event_type=event_type,
            risk_level=risk_level,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
            additional_data=additional_data,
            suspicious_activity_id=suspicious_activity_id,
            location_data=location_data or {},
            device_fingerprint=device_fingerprint,
            session_id=session_id
        )
        
        # Şüpheli aktivite tespiti
        if ip_address and event_type == 'login_failed':
            # Import burada yapılıyor circular import'u önlemek için
            from .models import SuspiciousActivity
            SuspiciousActivity.detect_suspicious_login_attempts(ip_address)
        
        if ip_address and event_type in ['login_success', 'login_failed', 'password_change']:
            from .models import SuspiciousActivity
            SuspiciousActivity.detect_rapid_requests(ip_address)
        
        return log_entry


class AccountLockout(models.Model):
    """Hesap kilitleme modeli"""
    LOCKOUT_REASONS = [
        ('failed_login', 'Çoklu Başarısız Giriş'),
        ('failed_2fa', 'Çoklu 2FA Hatası'),
        ('suspicious_activity', 'Şüpheli Aktivite'),
        ('admin_action', 'Yönetici İşlemi'),
        ('security_breach', 'Güvenlik İhlali'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='lockout')
    reason = models.CharField(max_length=20, choices=LOCKOUT_REASONS)
    locked_at = models.DateTimeField(auto_now_add=True)
    unlock_at = models.DateTimeField(null=True, blank=True)
    is_permanent = models.BooleanField(default=False)
    failed_attempts = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Hesap Kilidi'
        verbose_name_plural = 'Hesap Kilitleri'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_reason_display()}"
    
    def is_locked(self):
        """Hesabın kilitli olup olmadığını kontrol et"""
        if self.is_permanent:
            return True
        if self.unlock_at and timezone.now() < self.unlock_at:
            return True
        return False
    
    def unlock(self):
        """Hesap kilidini aç"""
        self.unlock_at = timezone.now()
        self.save()
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='account_unlocked',
            user=self.user,
            description=f'Hesap kilidi açıldı: {self.get_reason_display()}'
        )
    
    @classmethod
    def lock_account(cls, user, reason, duration_minutes=None, ip_address=None, description=''):
        """Hesabı kilitle"""
        lockout, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'reason': reason,
                'ip_address': ip_address,
                'description': description
            }
        )
        
        if not created:
            lockout.reason = reason
            lockout.locked_at = timezone.now()
            lockout.ip_address = ip_address
            lockout.description = description
        
        if duration_minutes:
            lockout.unlock_at = timezone.now() + timedelta(minutes=duration_minutes)
            lockout.is_permanent = False
        else:
            lockout.is_permanent = True
        
        lockout.save()
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='account_locked',
            user=user,
            ip_address=ip_address,
            description=f'Hesap kilitlendi: {description}',
            risk_level='high'
        )
        
        return lockout


class UserSecuritySettings(models.Model):
    """Kullanıcı güvenlik ayarları"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_settings')
    two_factor_enabled = models.BooleanField(default=False)
    backup_email = models.EmailField(blank=True)
    last_password_change = models.DateTimeField(null=True, blank=True)
    password_history = models.JSONField(default=list, blank=True)  # Son 5 şifrenin hash'i
    login_notifications = models.BooleanField(default=True)
    suspicious_activity_alerts = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Kullanıcı Güvenlik Ayarları'
        verbose_name_plural = 'Kullanıcı Güvenlik Ayarları'
    
    def __str__(self):
        return f"{self.user.username} - Güvenlik Ayarları"
    
    def add_password_to_history(self, password_hash):
        """Şifre geçmişine ekle (son 5 şifreyi tut)"""
        if not self.password_history:
            self.password_history = []
        
        self.password_history.insert(0, password_hash)
        self.password_history = self.password_history[:5]  # Son 5 şifreyi tut
        self.last_password_change = timezone.now()
        self.save()
    
    def is_password_in_history(self, password_hash):
        """Şifrenin geçmişte kullanılıp kullanılmadığını kontrol et"""
        return password_hash in (self.password_history or [])


class CaptchaChallenge(models.Model):
    """CAPTCHA meydan okuma modeli"""
    CHALLENGE_TYPES = [
        ('math', 'Matematik İşlemi'),
        ('text', 'Metin Doğrulama'),
    ]
    
    session_key = models.CharField(max_length=40, db_index=True)
    challenge_type = models.CharField(max_length=10, choices=CHALLENGE_TYPES, default='math')
    question = models.CharField(max_length=200)
    answer = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_solved = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'CAPTCHA Meydan Okuma'
        verbose_name_plural = 'CAPTCHA Meydan Okumaları'
    
    def __str__(self):
        return f"CAPTCHA - {self.session_key[:8]}... - {self.question}"
    
    @classmethod
    def generate_math_challenge(cls, session_key, ip_address=None):
        """Matematik tabanlı CAPTCHA oluştur"""
        import random
        
        # Basit matematik işlemleri
        operations = [
            ('+', lambda a, b: a + b),
            ('-', lambda a, b: a - b),
            ('*', lambda a, b: a * b),
        ]
        
        # Rastgele sayılar ve işlem seç
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        op_symbol, op_func = random.choice(operations)
        
        # Çıkarma işleminde negatif sonuç olmasın
        if op_symbol == '-' and num1 < num2:
            num1, num2 = num2, num1
        
        # Çarpma işleminde sayıları küçük tut
        if op_symbol == '*':
            num1 = random.randint(1, 10)
            num2 = random.randint(1, 10)
        
        question = f"{num1} {op_symbol} {num2} = ?"
        answer = str(op_func(num1, num2))
        
        # Eski CAPTCHA'ları temizle
        cls.objects.filter(
            session_key=session_key,
            expires_at__lt=timezone.now()
        ).delete()
        
        # Yeni CAPTCHA oluştur
        expires_at = timezone.now() + timedelta(minutes=10)
        
        return cls.objects.create(
            session_key=session_key,
            challenge_type='math',
            question=question,
            answer=answer,
            expires_at=expires_at,
            ip_address=ip_address
        )
    
    def is_valid(self):
        """CAPTCHA'nın geçerli olup olmadığını kontrol et"""
        return (
            not self.is_solved and 
            timezone.now() < self.expires_at and
            self.attempts < 5
        )
    
    def verify_answer(self, user_answer):
        """Kullanıcının cevabını doğrula"""
        self.attempts += 1
        
        if str(user_answer).strip() == self.answer:
            self.is_solved = True
            self.save()
            return True
        
        self.save()
        return False
    
    @classmethod
    def cleanup_expired(cls):
        """Süresi dolmuş CAPTCHA'ları temizle"""
        expired_count = cls.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        return expired_count


class SuspiciousActivity(models.Model):
    """Şüpheli aktivite tespit ve takip modeli"""
    ACTIVITY_TYPES = [
        ('multiple_failed_login', 'Çoklu Başarısız Giriş'),
        ('unusual_location', 'Olağandışı Konum'),
        ('unusual_time', 'Olağandışı Zaman'),
        ('multiple_devices', 'Çoklu Cihaz Kullanımı'),
        ('rapid_requests', 'Hızlı İstekler'),
        ('password_spray', 'Şifre Püskürtme'),
        ('credential_stuffing', 'Kimlik Bilgisi Doldurma'),
        ('bot_activity', 'Bot Aktivitesi'),
        ('unusual_user_agent', 'Olağandışı User Agent'),
        ('tor_usage', 'Tor Kullanımı'),
        ('vpn_usage', 'VPN Kullanımı'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Düşük'),
        ('medium', 'Orta'),
        ('high', 'Yüksek'),
        ('critical', 'Kritik'),
    ]
    
    STATUS_CHOICES = [
        ('detected', 'Tespit Edildi'),
        ('investigating', 'İnceleniyor'),
        ('confirmed', 'Doğrulandı'),
        ('false_positive', 'Yanlış Pozitif'),
        ('resolved', 'Çözüldü'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suspicious_activities', null=True, blank=True)
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='medium')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='detected')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    location_info = models.JSONField(default=dict, blank=True)  # Ülke, şehir, ISP bilgileri
    detection_data = models.JSONField(default=dict, blank=True)  # Tespit detayları
    risk_score = models.PositiveIntegerField(default=0)  # 0-100 arası risk skoru
    auto_blocked = models.BooleanField(default=False)  # Otomatik engellenme durumu
    admin_notified = models.BooleanField(default=False)  # Admin bilgilendirilme durumu
    user_notified = models.BooleanField(default=False)  # Kullanıcı bilgilendirilme durumu
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)  # Admin notları
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Şüpheli Aktivite'
        verbose_name_plural = 'Şüpheli Aktiviteler'
        indexes = [
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['severity', 'status']),
        ]
    
    def __str__(self):
        user_info = self.user.username if self.user else 'Anonim'
        return f"{user_info} - {self.get_activity_type_display()} ({self.severity})"
    
    @classmethod
    def detect_suspicious_login_attempts(cls, ip_address, time_window_minutes=15, threshold=5):
        """Belirli IP'den çok sayıda başarısız giriş denemesi tespit et"""
        from datetime import timedelta
        
        time_threshold = timezone.now() - timedelta(minutes=time_window_minutes)
        
        # Son X dakikada bu IP'den başarısız giriş sayısını say
        failed_attempts = SecurityLog.objects.filter(
            event_type='login_failed',
            ip_address=ip_address,
            created_at__gte=time_threshold
        ).count()
        
        if failed_attempts >= threshold:
            # Şüpheli aktivite kaydı oluştur
            activity = cls.objects.create(
                activity_type='multiple_failed_login',
                severity='high' if failed_attempts >= threshold * 2 else 'medium',
                ip_address=ip_address,
                detection_data={
                    'failed_attempts': failed_attempts,
                    'time_window': time_window_minutes,
                    'threshold': threshold
                },
                risk_score=min(100, failed_attempts * 10)
            )
            
            # Güvenlik logu
            SecurityLog.log_event(
                event_type='suspicious_activity',
                ip_address=ip_address,
                description=f'Şüpheli giriş denemeleri tespit edildi: {failed_attempts} başarısız deneme',
                risk_level='high',
                suspicious_activity_id=activity.id
            )
            
            return activity
        
        return None
    
    @classmethod
    def detect_unusual_location(cls, user, ip_address, current_location):
        """Olağandışı konum tespit et"""
        # Son 30 gün içindeki giriş konumlarını kontrol et
        recent_logs = SecurityLog.objects.filter(
            user=user,
            event_type='login_success',
            created_at__gte=timezone.now() - timedelta(days=30)
        ).exclude(additional_data__location__country__isnull=True)
        
        known_countries = set()
        for log in recent_logs:
            location = log.additional_data.get('location', {})
            if location.get('country'):
                known_countries.add(location['country'])
        
        current_country = current_location.get('country')
        
        # Eğer yeni bir ülkeden giriş yapılıyorsa şüpheli aktivite olarak işaretle
        if current_country and current_country not in known_countries and known_countries:
            activity = cls.objects.create(
                user=user,
                activity_type='unusual_location',
                severity='medium',
                ip_address=ip_address,
                location_info=current_location,
                detection_data={
                    'known_countries': list(known_countries),
                    'new_country': current_country
                },
                risk_score=60
            )
            
            return activity
        
        return None
    
    @classmethod
    def detect_rapid_requests(cls, ip_address, time_window_seconds=60, threshold=50):
        """Hızlı istekler (potansiyel bot aktivitesi) tespit et"""
        time_threshold = timezone.now() - timedelta(seconds=time_window_seconds)
        
        # Son X saniyede bu IP'den gelen istek sayısını say
        request_count = SecurityLog.objects.filter(
            ip_address=ip_address,
            created_at__gte=time_threshold
        ).count()
        
        if request_count >= threshold:
            activity = cls.objects.create(
                activity_type='rapid_requests',
                severity='high',
                ip_address=ip_address,
                detection_data={
                    'request_count': request_count,
                    'time_window': time_window_seconds,
                    'threshold': threshold
                },
                risk_score=min(100, request_count * 2),
                auto_blocked=True  # Otomatik engelle
            )
            
            return activity
        
        return None
    
    def calculate_risk_score(self):
        """Risk skorunu hesapla"""
        base_scores = {
            'multiple_failed_login': 40,
            'unusual_location': 30,
            'unusual_time': 20,
            'multiple_devices': 25,
            'rapid_requests': 60,
            'password_spray': 70,
            'credential_stuffing': 80,
            'bot_activity': 50,
            'unusual_user_agent': 15,
            'tor_usage': 45,
            'vpn_usage': 25,
        }
        
        base_score = base_scores.get(self.activity_type, 30)
        
        # Severity çarpanı
        severity_multipliers = {
            'low': 0.5,
            'medium': 1.0,
            'high': 1.5,
            'critical': 2.0,
        }
        
        multiplier = severity_multipliers.get(self.severity, 1.0)
        
        # Kullanıcının geçmiş aktivitelerine göre artış
        if self.user:
            recent_activities = SuspiciousActivity.objects.filter(
                user=self.user,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            if recent_activities > 3:
                multiplier += 0.5
        
        final_score = min(100, int(base_score * multiplier))
        
        if self.risk_score != final_score:
            self.risk_score = final_score
            self.save(update_fields=['risk_score'])
        
        return final_score
    
    def mark_as_resolved(self, notes=''):
        """Şüpheli aktiviteyi çözüldü olarak işaretle"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        if notes:
            self.notes = notes
        self.save()
    
    def notify_admin(self):
        """Yöneticileri bilgilendir"""
        if not self.admin_notified and self.severity in ['high', 'critical']:
            # E-posta bildirimi gönder (implement edilecek)
            self.admin_notified = True
            self.save(update_fields=['admin_notified'])
    
    def notify_user(self):
        """Kullanıcıyı bilgilendir"""
        if not self.user_notified and self.user and self.severity in ['medium', 'high', 'critical']:
            # Kullanıcıya güvenlik uyarısı gönder
            from .views import send_security_alert
            
            try:
                send_security_alert(
                    user=self.user,
                    alert_type='suspicious_activity',
                    details={
                        'activity_type': self.get_activity_type_display(),
                        'severity': self.get_severity_display(),
                        'ip_address': self.ip_address,
                        'timestamp': self.created_at.strftime('%d.%m.%Y %H:%M'),
                        'location': self.location_info
                    }
                )
                self.user_notified = True
                self.save(update_fields=['user_notified'])
            except Exception as e:
                SecurityLog.log_event(
                    event_type='suspicious_activity',
                    user=self.user,
                    description=f'Şüpheli aktivite bildirimi gönderilemedi: {str(e)}',
                    risk_level='medium'
                )


class DeviceInfo(models.Model):
    """Kullanıcı cihaz bilgileri modeli"""
    
    DEVICE_TYPES = [
        ('desktop', 'Masaüstü'),
        ('mobile', 'Mobil'),
        ('tablet', 'Tablet'),
        ('unknown', 'Bilinmiyor'),
    ]
    
    TRUST_LEVELS = [
        ('trusted', 'Güvenilir'),
        ('suspicious', 'Şüpheli'),
        ('blocked', 'Engellenmiş'),
        ('unknown', 'Bilinmiyor'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_fingerprint = models.CharField(max_length=255, unique=True, db_index=True)
    device_name = models.CharField(max_length=200, blank=True)  # Kullanıcı tarafından verilen isim
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPES, default='unknown')
    browser_name = models.CharField(max_length=100, blank=True)
    browser_version = models.CharField(max_length=50, blank=True)
    os_name = models.CharField(max_length=100, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    screen_resolution = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    language = models.CharField(max_length=10, blank=True)
    trust_level = models.CharField(max_length=15, choices=TRUST_LEVELS, default='unknown')
    is_active = models.BooleanField(default=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    last_location = models.JSONField(default=dict, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-last_seen']
        verbose_name = 'Cihaz Bilgisi'
        verbose_name_plural = 'Cihaz Bilgileri'
        indexes = [
            models.Index(fields=['user', 'trust_level']),
            models.Index(fields=['device_fingerprint']),
            models.Index(fields=['last_seen']),
        ]
    
    def __str__(self):
        device_name = self.device_name or f"{self.browser_name} on {self.os_name}"
        return f"{self.user.username} - {device_name}"
    
    def update_activity(self, ip_address=None, location_data=None):
        """Cihaz aktivitesini güncelle"""
        self.last_seen = timezone.now()
        self.login_count += 1
        if ip_address:
            self.last_ip = ip_address
        if location_data:
            self.last_location = location_data
        self.save()
    
    def mark_as_trusted(self):
        """Cihazı güvenilir olarak işaretle"""
        self.trust_level = 'trusted'
        self.save()
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='device_trusted',
            user=self.user,
            description=f'Cihaz güvenilir olarak işaretlendi: {self}',
            device_fingerprint=self.device_fingerprint
        )
    
    def mark_as_suspicious(self, reason=''):
        """Cihazı şüpheli olarak işaretle"""
        self.trust_level = 'suspicious'
        self.save()
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='device_suspicious',
            user=self.user,
            description=f'Cihaz şüpheli olarak işaretlendi: {self}. Sebep: {reason}',
            risk_level='medium',
            device_fingerprint=self.device_fingerprint
        )
    
    def block_device(self, reason=''):
        """Cihazı engelle"""
        self.trust_level = 'blocked'
        self.is_active = False
        self.save()
        
        # Aktif oturumları sonlandır
        UserSession.objects.filter(
            user=self.user,
            device_fingerprint=self.device_fingerprint,
            is_active=True
        ).update(is_active=False, ended_at=timezone.now())
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='device_blocked',
            user=self.user,
            description=f'Cihaz engellendi: {self}. Sebep: {reason}',
            risk_level='high',
            device_fingerprint=self.device_fingerprint
        )
    
    @classmethod
    def get_or_create_device(cls, user, device_fingerprint, device_data=None):
        """Cihaz bilgisini al veya oluştur"""
        device, created = cls.objects.get_or_create(
            user=user,
            device_fingerprint=device_fingerprint,
            defaults=device_data or {}
        )
        
        if created:
            # Yeni cihaz tespit edildi
            SecurityLog.log_event(
                event_type='new_device_detected',
                user=user,
                description=f'Yeni cihaz tespit edildi: {device}',
                risk_level='medium',
                device_fingerprint=device_fingerprint
            )
            
            # Kullanıcıya bildirim gönder
            if user.security_settings.login_notifications:
                device.notify_new_device()
        
        return device, created
    
    def notify_new_device(self):
        """Yeni cihaz bildirimi gönder"""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            subject = 'Yeni Cihaz Girişi Tespit Edildi'
            message = f"""
            Merhaba {self.user.first_name or self.user.username},
            
            Hesabınızda yeni bir cihazdan giriş tespit edildi:
            
            Cihaz: {self.browser_name} on {self.os_name}
            Zaman: {self.first_seen.strftime('%d.%m.%Y %H:%M:%S')}
            IP Adresi: {self.last_ip}
            Konum: {self.last_location.get('country', 'Bilinmiyor')}
            
            Bu giriş sizin tarafınızdan yapılmadıysa, lütfen derhal şifrenizi değiştirin.
            
            Güvenlik ekibi
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.user.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Yeni cihaz bildirim hatası: {e}")


class UserSession(models.Model):
    """Kullanıcı oturum yönetimi modeli"""
    
    SESSION_TYPES = [
        ('web', 'Web Tarayıcı'),
        ('mobile_app', 'Mobil Uygulama'),
        ('api', 'API'),
        ('admin', 'Yönetici Paneli'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_sessions')
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    device_fingerprint = models.CharField(max_length=255, db_index=True)
    session_type = models.CharField(max_length=15, choices=SESSION_TYPES, default='web')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    location_data = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    is_authenticated = models.BooleanField(default=False)
    two_factor_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Güvenlik bilgileri
    login_method = models.CharField(max_length=50, blank=True)  # password, 2fa, social_auth
    risk_score = models.PositiveIntegerField(default=0)  # 0-100 arası
    is_suspicious = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-last_activity']
        verbose_name = 'Kullanıcı Oturumu'
        verbose_name_plural = 'Kullanıcı Oturumları'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['device_fingerprint']),
            models.Index(fields=['last_activity']),
            models.Index(fields=['is_suspicious']),
        ]
    
    def __str__(self):
        status = "Aktif" if self.is_active else "Sonlandırılmış"
        return f"{self.user.username} - {self.get_session_type_display()} ({status})"
    
    def update_activity(self):
        """Oturum aktivitesini güncelle"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def end_session(self, reason='user_logout'):
        """Oturumu sonlandır"""
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='session_ended',
            user=self.user,
            description=f'Oturum sonlandırıldı. Sebep: {reason}',
            session_id=self.session_key,
            device_fingerprint=self.device_fingerprint
        )
    
    def mark_as_suspicious(self, reason=''):
        """Oturumu şüpheli olarak işaretle"""
        self.is_suspicious = True
        self.risk_score = min(self.risk_score + 25, 100)
        self.save()
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='session_suspicious',
            user=self.user,
            description=f'Oturum şüpheli olarak işaretlendi: {reason}',
            risk_level='medium',
            session_id=self.session_key,
            device_fingerprint=self.device_fingerprint
        )
    
    def calculate_risk_score(self):
        """Oturum risk skorunu hesapla"""
        risk_score = 0
        
        # Cihaz güven seviyesi
        try:
            device = DeviceInfo.objects.get(
                user=self.user,
                device_fingerprint=self.device_fingerprint
            )
            if device.trust_level == 'blocked':
                risk_score += 50
            elif device.trust_level == 'suspicious':
                risk_score += 30
            elif device.trust_level == 'unknown':
                risk_score += 20
        except DeviceInfo.DoesNotExist:
            risk_score += 25  # Bilinmeyen cihaz
        
        # Oturum süresi
        if self.created_at:
            session_duration = timezone.now() - self.created_at
            if session_duration.total_seconds() > 86400:  # 24 saat
                risk_score += 15
        
        # 2FA doğrulaması
        if not self.two_factor_verified and self.user.security_settings.two_factor_enabled:
            risk_score += 20
        
        # Şüpheli aktivite geçmişi
        recent_suspicious = SuspiciousActivity.objects.filter(
            user=self.user,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        risk_score += min(recent_suspicious * 10, 30)
        
        self.risk_score = min(risk_score, 100)
        self.save(update_fields=['risk_score'])
        
        return self.risk_score
    
    @classmethod
    def create_session(cls, user, session_key, device_fingerprint, ip_address=None, 
                      user_agent='', location_data=None, session_type='web'):
        """Yeni oturum oluştur"""
        # Eski oturumları temizle
        cls.cleanup_expired_sessions()
        
        # Yeni oturum oluştur
        session = cls.objects.create(
            user=user,
            session_key=session_key,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent,
            location_data=location_data or {},
            session_type=session_type,
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        # Risk skorunu hesapla
        session.calculate_risk_score()
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='session_created',
            user=user,
            ip_address=ip_address,
            description=f'Yeni oturum oluşturuldu: {session_type}',
            session_id=session_key,
            device_fingerprint=device_fingerprint,
            location_data=location_data
        )
        
        return session
    
    @classmethod
    def cleanup_expired_sessions(cls):
        """Süresi dolmuş oturumları temizle"""
        expired_sessions = cls.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        )
        
        for session in expired_sessions:
            session.end_session('expired')
    
    @classmethod
    def get_active_sessions(cls, user):
        """Kullanıcının aktif oturumlarını getir"""
        return cls.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('user')
    
    @classmethod
    def end_all_sessions(cls, user, except_session=None, reason='security_action'):
        """Kullanıcının tüm oturumlarını sonlandır"""
        sessions = cls.objects.filter(
            user=user,
            is_active=True
        )
        
        if except_session:
            sessions = sessions.exclude(session_key=except_session)
        
        for session in sessions:
            session.end_session(reason)
        
        # Güvenlik logu
        SecurityLog.log_event(
            event_type='all_sessions_ended',
            user=user,
            description=f'Tüm oturumlar sonlandırıldı. Sebep: {reason}',
            risk_level='medium'
        )