from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import UserSecuritySettings, SecurityLog, EmailVerificationCode, CaptchaChallenge
import re


class SecureLoginForm(AuthenticationForm):
    """Güvenli giriş formu"""
    
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kullanıcı adı veya e-posta',
            'autocomplete': 'username',
            'required': True
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Şifre',
            'autocomplete': 'current-password',
            'required': True
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    captcha = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'CAPTCHA kodunu girin',
            'autocomplete': 'off'
        })
    )
    
    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.captcha_required = False
        super().__init__(request, *args, **kwargs)
        
        # CAPTCHA gerekli mi kontrol et
        if request and hasattr(request, 'session'):
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            
            # Başarısız giriş denemesi sayısını kontrol et
            failed_attempts = request.session.get('failed_login_attempts', 0)
            if failed_attempts >= 3:
                self.captcha_required = True
                self.fields['captcha'].required = True
    
    def clean_captcha(self):
        captcha_answer = self.cleaned_data.get('captcha')
        
        if self.captcha_required:
            if not captcha_answer:
                raise ValidationError('CAPTCHA doğrulaması gereklidir.')
            
            # Session key'i al
            session_key = None
            if self.request and hasattr(self.request, 'session'):
                session_key = self.request.session.session_key
            
            if not session_key:
                raise ValidationError('Oturum hatası. Lütfen sayfayı yenileyin.')
            
            # CAPTCHA'yı doğrula
            try:
                captcha = CaptchaChallenge.objects.filter(
                    session_key=session_key,
                    is_solved=False
                ).latest('created_at')
                
                if not captcha.is_valid():
                    raise ValidationError('CAPTCHA süresi dolmuş veya geçersiz. Lütfen yenileyin.')
                
                if not captcha.verify_answer(captcha_answer):
                    raise ValidationError('CAPTCHA cevabı yanlış. Lütfen tekrar deneyin.')
                    
            except CaptchaChallenge.DoesNotExist:
                raise ValidationError('CAPTCHA bulunamadı. Lütfen sayfayı yenileyin.')
        
        return captcha_answer


class SecureRegistrationForm(UserCreationForm):
    """Güvenli kayıt formu"""
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ad',
            'autocomplete': 'given-name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Soyad',
            'autocomplete': 'family-name'
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'E-posta adresi',
            'autocomplete': 'email'
        })
    )
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kullanıcı adı',
            'autocomplete': 'username'
        })
    )
    
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Şifre',
            'autocomplete': 'new-password'
        })
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Şifre tekrarı',
            'autocomplete': 'new-password'
        })
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    captcha = forms.CharField(
        required=True,
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'CAPTCHA kodunu girin',
            'autocomplete': 'off'
        })
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean_captcha(self):
        captcha_answer = self.cleaned_data.get('captcha')
        
        if not captcha_answer:
            raise ValidationError('CAPTCHA doğrulaması gereklidir.')
        
        # Session key'i al
        session_key = None
        if self.request and hasattr(self.request, 'session'):
            session_key = self.request.session.session_key
            if not session_key:
                self.request.session.create()
                session_key = self.request.session.session_key
        
        if not session_key:
            raise ValidationError('Oturum hatası. Lütfen sayfayı yenileyin.')
        
        # CAPTCHA'yı doğrula
        try:
            captcha = CaptchaChallenge.objects.filter(
                session_key=session_key,
                is_solved=False
            ).latest('created_at')
            
            if not captcha.is_valid():
                raise ValidationError('CAPTCHA süresi dolmuş veya geçersiz. Lütfen yenileyin.')
            
            if not captcha.verify_answer(captcha_answer):
                raise ValidationError('CAPTCHA cevabı yanlış. Lütfen tekrar deneyin.')
                
        except CaptchaChallenge.DoesNotExist:
            raise ValidationError('CAPTCHA bulunamadı. Lütfen sayfayı yenileyin.')
        
        return captcha_answer
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Bu e-posta adresi zaten kullanılıyor.')
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError('Bu kullanıcı adı zaten kullanılıyor.')
        return username
    
    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if password1:
            # Django'nun varsayılan şifre doğrulaması
            validate_password(password1)
            
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
        
        return password1


class TwoFactorVerifyForm(forms.Form):
    """İki faktörlü kimlik doğrulama formu"""
    
    verification_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric',
            'maxlength': '6'
        })
    )
    
    def clean_verification_code(self):
        code = self.cleaned_data.get('verification_code')
        if not code.isdigit():
            raise ValidationError('Doğrulama kodu sadece rakam içermelidir.')
        return code


class SecuritySettingsForm(forms.ModelForm):
    """Kullanıcı güvenlik ayarları formu"""
    
    class Meta:
        model = UserSecuritySettings
        fields = ['two_factor_enabled', 'backup_email', 'login_notifications', 'suspicious_activity_alerts']
        widgets = {
            'backup_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'two_factor_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'login_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'suspicious_activity_alerts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'two_factor_enabled': 'İki Faktörlü Kimlik Doğrulamayı Etkinleştir',
            'backup_email': 'Yedek E-posta Adresi',
            'login_notifications': 'Giriş Bildirimlerini Etkinleştir',
            'suspicious_activity_alerts': 'Şüpheli Aktivite Uyarılarını Etkinleştir',
        }
    
    def clean_backup_email(self):
        backup_email = self.cleaned_data.get('backup_email')
        
        if backup_email:
            # Ana e-posta ile aynı olmasın
            if backup_email == self.instance.user.email:
                raise ValidationError('Yedek e-posta ana e-posta ile aynı olamaz.')
            
            # Başka kullanıcının ana e-postası olmasın
            if User.objects.filter(email=backup_email).exists():
                raise ValidationError('Bu e-posta adresi başka bir kullanıcı tarafından kullanılıyor.')
        
        return backup_email


class ChangePasswordForm(forms.Form):
    """Şifre değiştirme formu"""
    
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mevcut şifre',
            'autocomplete': 'current-password'
        })
    )
    
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Yeni şifre',
            'autocomplete': 'new-password'
        })
    )
    
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Yeni şifre tekrarı',
            'autocomplete': 'new-password'
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise ValidationError('Mevcut şifre yanlış.')
        return current_password
    
    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        if password:
            # Django'nun varsayılan şifre doğrulaması
            validate_password(password, self.user)
            
            # Ek güvenlik kontrolleri
            if len(password) < 12:
                raise ValidationError('Şifre en az 12 karakter olmalıdır.')
            
            # Karmaşıklık kontrolleri
            if not re.search(r'[A-Z]', password):
                raise ValidationError('Şifre en az bir büyük harf içermelidir.')
            
            if not re.search(r'[a-z]', password):
                raise ValidationError('Şifre en az bir küçük harf içermelidir.')
            
            if not re.search(r'\d', password):
                raise ValidationError('Şifre en az bir rakam içermelidir.')
            
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise ValidationError('Şifre en az bir özel karakter içermelidir.')
            
            # Şifre geçmişi kontrolü
            try:
                from django.contrib.auth.hashers import check_password
                settings = UserSecuritySettings.objects.get(user=self.user)
                
                for old_hash in (settings.password_history or []):
                    if check_password(password, old_hash):
                        raise ValidationError('Bu şifreyi daha önce kullandınız. Lütfen farklı bir şifre seçin.')
            except UserSecuritySettings.DoesNotExist:
                pass
            
            # Yaygın şifreler kontrolü
            common_passwords = [
                'password', '123456', '123456789', 'qwerty', 'abc123',
                'password123', 'admin', 'letmein', 'welcome', 'monkey'
            ]
            if password.lower() in common_passwords:
                raise ValidationError('Bu şifre çok yaygın kullanılıyor. Lütfen daha güvenli bir şifre seçin.')
        
        return password
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Şifreler eşleşmiyor.')
        return password2
    
    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get('current_password')
        new_password1 = cleaned_data.get('new_password1')
        
        if current_password and new_password1 and current_password == new_password1:
            raise ValidationError('Yeni şifre mevcut şifre ile aynı olamaz.')
        
        return cleaned_data


class PasswordResetRequestForm(forms.Form):
    """Şifre sıfırlama isteği formu"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'E-posta adresinizi girin',
            'autocomplete': 'email'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError('Bu e-posta adresi ile kayıtlı kullanıcı bulunamadı.')
        return email


class PasswordResetConfirmForm(forms.Form):
    """Şifre sıfırlama onay formu"""
    
    verification_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'autocomplete': 'off'
        })
    )
    
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Yeni şifre'
        })
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Yeni şifre tekrarı'
        })
    )
    
    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_verification_code(self):
        code = self.cleaned_data.get('verification_code')
        if not code.isdigit():
            raise ValidationError('Doğrulama kodu sadece rakam içermelidir.')
        return code
    
    def clean_new_password(self):
        password = self.cleaned_data.get('new_password')
        if password and self.user:
            # Django'nun varsayılan şifre doğrulaması
            validate_password(password, self.user)
            
            # Ek güvenlik kontrolleri
            if len(password) < 12:
                raise ValidationError('Şifre en az 12 karakter olmalıdır.')
            
            # Karmaşıklık kontrolleri
            if not re.search(r'[A-Z]', password):
                raise ValidationError('Şifre en az bir büyük harf içermelidir.')
            
            if not re.search(r'[a-z]', password):
                raise ValidationError('Şifre en az bir küçük harf içermelidir.')
            
            if not re.search(r'\d', password):
                raise ValidationError('Şifre en az bir rakam içermelidir.')
            
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise ValidationError('Şifre en az bir özel karakter içermelidir.')
            
            # Şifre geçmişi kontrolü
            try:
                from django.contrib.auth.hashers import check_password
                settings = UserSecuritySettings.objects.get(user=self.user)
                
                for old_hash in (settings.password_history or []):
                    if check_password(password, old_hash):
                        raise ValidationError('Bu şifreyi daha önce kullandınız. Lütfen farklı bir şifre seçin.')
            except UserSecuritySettings.DoesNotExist:
                pass
            
            # Yaygın şifreler kontrolü
            common_passwords = [
                'password', '123456', '123456789', 'qwerty', 'abc123',
                'password123', 'admin', 'letmein', 'welcome', 'monkey'
            ]
            if password.lower() in common_passwords:
                raise ValidationError('Bu şifre çok yaygın kullanılıyor. Lütfen daha güvenli bir şifre seçin.')
        
        return password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError('Şifreler eşleşmiyor.')
        
        return cleaned_data


class SecurityLogFilterForm(forms.Form):
    """Güvenlik log filtreleme formu"""
    
    ACTION_CHOICES = [
        ('', 'Tüm Eylemler'),
        ('login_success', 'Başarılı Giriş'),
        ('failed_login', 'Başarısız Giriş'),
        ('login_2fa_success', '2FA Başarılı'),
        ('login_2fa_failed', '2FA Başarısız'),
        ('logout', 'Çıkış'),
        ('password_changed', 'Şifre Değiştirildi'),
        ('registration', 'Kayıt'),
        ('security_settings_updated', 'Güvenlik Ayarları Güncellendi'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    ip_address = forms.CharField(
        required=False,
        max_length=45,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'IP adresi'
        })
    )