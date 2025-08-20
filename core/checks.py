from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Warning, Tags, register
from django.core.checks.messages import CheckMessage
from django.urls import reverse, NoReverseMatch


def _is_prod() -> bool:
    """Üretim ortamı kontrolü"""
    return not getattr(settings, "DEBUG", True)


@register(Tags.security)
def security_settings_check(app_configs, **kwargs) -> list[CheckMessage]:
    """Güvenlik ayarları kontrolü"""
    msgs: list[CheckMessage] = []
    
    if _is_prod():
        if not getattr(settings, "ALLOWED_HOSTS", []):
            msgs.append(Error("ALLOWED_HOSTS boş. Üretimde zorunludur.", id="core.S001"))
        
        if not getattr(settings, "SECURE_SSL_REDIRECT", False):
            msgs.append(Error("SECURE_SSL_REDIRECT etkin değil.", id="core.S002"))
        
        if not getattr(settings, "SESSION_COOKIE_SECURE", False):
            msgs.append(Error("SESSION_COOKIE_SECURE etkin değil.", id="core.S003"))
        
        if not getattr(settings, "CSRF_COOKIE_SECURE", False):
            msgs.append(Error("CSRF_COOKIE_SECURE etkin değil.", id="core.S004"))
        
        hsts = getattr(settings, "SECURE_HSTS_SECONDS", 0)
        if not hsts or hsts < 31536000:
            msgs.append(Warning("SECURE_HSTS_SECONDS düşük/kapalı (öneri ≥ 31536000).", id="core.S005"))
        
        if not getattr(settings, "CSRF_TRUSTED_ORIGINS", []):
            msgs.append(Warning("CSRF_TRUSTED_ORIGINS boş.", id="core.S006"))
    
    return msgs


@register(Tags.compatibility)
def whitenoise_check(app_configs, **kwargs) -> list[CheckMessage]:
    """WhiteNoise middleware kontrolü"""
    msgs: list[CheckMessage] = []
    
    mw = [m.lower() for m in getattr(settings, "MIDDLEWARE", [])]
    if not any("whitenoise.middleware.whitenoisemiddleware" in m for m in mw):
        msgs.append(Warning("WhiteNoise middleware etkin değil; statik dosyalar prod'da yavaş olabilir.", id="core.W001"))
    
    return msgs


@register(Tags.models)
def migrations_applied_check(app_configs, **kwargs) -> list[CheckMessage]:
    """Hafif kontrol: MIGRATION_MODULES ile migration devre dışı mı?"""
    msgs: list[CheckMessage] = []
    
    if getattr(settings, "MIGRATION_MODULES", None) == {"all": None}:
        msgs.append(Warning("Migrations devre dışı (MIGRATION_MODULES).", id="core.M001"))
    
    return msgs


@register(Tags.caches)
def ratelimit_check(app_configs, **kwargs) -> list[CheckMessage]:
    """Rate limit ve cache kontrolü"""
    msgs: list[CheckMessage] = []
    
    if getattr(settings, "RATELIMIT_ENABLE", False):
        if not getattr(settings, "CACHES", None):
            msgs.append(Warning("Rate limit etkin ama CACHES yapılandırılmamış.", id="core.R001"))
    
    return msgs


@register(Tags.security)
def email_settings_check(app_configs, **kwargs) -> list[CheckMessage]:
    """Email ayarları kontrolü"""
    msgs: list[CheckMessage] = []
    
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if "smtp" in backend.lower():
        needed = ("EMAIL_HOST", "EMAIL_PORT", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD")
        missing = [n for n in needed if not getattr(settings, n, None)]
        if missing:
            msgs.append(Error(f"SMTP backend aktif ama eksik ayarlar: {', '.join(missing)}", id="core.E001"))
        
        if not getattr(settings, "DEFAULT_FROM_EMAIL", None):
            msgs.append(Warning("DEFAULT_FROM_EMAIL tanımlı değil.", id="core.E002"))
    
    return msgs


@register(Tags.urls)
def payment_provider_check(app_configs, **kwargs) -> list[CheckMessage]:
    """Ödeme sağlayıcı kontrolü"""
    msgs: list[CheckMessage] = []
    
    provider = getattr(settings, "PAYMENT_PROVIDER", "mock").lower()
    
    # Callback URL reverse kontrolü
    for name in ("iyzico_callback", "paytr_callback"):
        try:
            reverse(name)
        except NoReverseMatch:
            msgs.append(Warning(f"URL name bulunamadı: {name}", id="core.P001"))
    
    if provider == "iyzico":
        required = ("IYZICO_API_KEY", "IYZICO_SECRET", "IYZICO_BASE_URL")
        missing = [k for k in required if not getattr(settings, k, None)]
        if missing:
            msgs.append(Error(f"İyzico seçili ama eksik ayarlar: {', '.join(missing)}", id="core.P002"))
    
    elif provider == "paytr":
        required = ("PAYTR_MERCHANT_ID", "PAYTR_MERCHANT_KEY", "PAYTR_MERCHANT_SALT", "PAYTR_BASE_URL")
        missing = [k for k in required if not getattr(settings, k, None)]
        if missing:
            msgs.append(Error(f"PayTR seçili ama eksik ayarlar: {', '.join(missing)}", id="core.P003"))
    
    return msgs


@register(Tags.compatibility)
def sentry_check(app_configs, **kwargs) -> list[CheckMessage]:
    """Sentry yapılandırma kontrolü"""
    msgs: list[CheckMessage] = []
    
    if _is_prod() and not getattr(settings, "SENTRY_DSN", None):
        msgs.append(Warning("SENTRY_DSN boş (önerilir).", id="core.N001"))
    
    return msgs