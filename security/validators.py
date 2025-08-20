from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import re


class CustomPasswordValidator:
    """
    Özel şifre doğrulayıcısı - güçlü şifre politikası uygular
    """
    
    def validate(self, password, user=None):
        errors = []
        
        # En az 8 karakter
        if len(password) < 8:
            errors.append(_("Şifre en az 8 karakter olmalıdır."))
        
        # En az bir büyük harf
        if not re.search(r'[A-Z]', password):
            errors.append(_("Şifre en az bir büyük harf içermelidir."))
        
        # En az bir küçük harf
        if not re.search(r'[a-z]', password):
            errors.append(_("Şifre en az bir küçük harf içermelidir."))
        
        # En az bir rakam
        if not re.search(r'\d', password):
            errors.append(_("Şifre en az bir rakam içermelidir."))
        
        # En az bir özel karakter
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append(_("Şifre en az bir özel karakter (!@#$%^&*(),.?\":{}|<>) içermelidir."))
        
        # Yaygın zayıf şifre kalıpları
        weak_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'abc123',
            r'admin',
            r'letmein',
            r'welcome',
        ]
        
        for pattern in weak_patterns:
            if re.search(pattern, password.lower()):
                errors.append(_(f"Şifre yaygın zayıf kalıplar içeremez: {pattern}"))
        
        # Kullanıcı bilgileriyle benzerlik kontrolü
        if user:
            user_info = [
                user.username.lower() if hasattr(user, 'username') else '',
                user.email.lower().split('@')[0] if hasattr(user, 'email') and user.email else '',
                user.first_name.lower() if hasattr(user, 'first_name') else '',
                user.last_name.lower() if hasattr(user, 'last_name') else '',
            ]
            
            for info in user_info:
                if info and len(info) > 2 and info in password.lower():
                    errors.append(_("Şifre kullanıcı bilgilerinizle benzer olamaz."))
                    break
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        return _(
            "Şifreniz en az 8 karakter olmalı ve şunları içermelidir: "
            "büyük harf, küçük harf, rakam ve özel karakter (!@#$%^&*(),.?\":{}|<>)."
        )


class PasswordHistoryValidator:
    """
    Şifre geçmişi doğrulayıcısı - son kullanılan şifrelerin tekrar kullanılmasını engeller
    """
    
    def __init__(self, history_count=5):
        self.history_count = history_count
    
    def validate(self, password, user=None):
        if not user or not hasattr(user, 'id'):
            return
        
        from .models import PasswordHistory
        from django.contrib.auth.hashers import check_password
        
        # Son kullanılan şifreleri kontrol et
        recent_passwords = PasswordHistory.objects.filter(
            user=user
        ).order_by('-created_at')[:self.history_count]
        
        for old_password in recent_passwords:
            if check_password(password, old_password.password_hash):
                raise ValidationError(
                    _(f"Bu şifre son {self.history_count} şifrenizden biri. Lütfen farklı bir şifre seçin.")
                )
    
    def get_help_text(self):
        return _(f"Şifreniz son {self.history_count} kullandığınız şifrelerden farklı olmalıdır.")


class PasswordStrengthValidator:
    """
    Şifre gücü doğrulayıcısı - şifre gücünü hesaplar ve minimum seviye gerektirir
    """
    
    def __init__(self, min_strength=3):
        self.min_strength = min_strength
    
    def validate(self, password, user=None):
        strength = self.calculate_strength(password)
        
        if strength < self.min_strength:
            raise ValidationError(
                _(f"Şifre gücü yetersiz. Minimum {self.min_strength}/5 seviyesinde olmalıdır. "
                  f"Mevcut seviye: {strength}/5")
            )
    
    def calculate_strength(self, password):
        """
        Şifre gücünü 1-5 arasında hesaplar
        """
        score = 0
        
        # Uzunluk puanı
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        
        # Karakter çeşitliliği puanı
        if re.search(r'[a-z]', password):
            score += 0.5
        if re.search(r'[A-Z]', password):
            score += 0.5
        if re.search(r'\d', password):
            score += 0.5
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 0.5
        
        # Karmaşıklık puanı
        unique_chars = len(set(password))
        if unique_chars >= len(password) * 0.7:  # %70 benzersiz karakter
            score += 1
        
        return min(5, int(score))
    
    def get_help_text(self):
        return _(f"Şifreniz en az {self.min_strength}/5 seviyesinde güçlü olmalıdır.")