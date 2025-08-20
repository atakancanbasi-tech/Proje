# payments/provider.py
from dataclasses import dataclass
import os
import hashlib
import hmac
import json
from urllib.parse import urlencode
from django.conf import settings

@dataclass
class ChargeResult:
    success: bool
    provider_ref: str | None = None
    message: str | None = None
    requires_redirect: bool = False
    form_html: str | None = None   # otomatik post eden HTML (iyzico/paytr)

class PaymentProvider:
    def __init__(self, settings):
        self.settings = settings

    def charge(self, *, amount: float, currency: str, order_ref: str) -> ChargeResult:
        raise NotImplementedError
    
    def initiate(self, order, amount, currency, request) -> ChargeResult:
        """Ödeme işlemini başlatır. Mock için direkt başarı, diğerleri için redirect form döner."""
        raise NotImplementedError
    
    def verify_callback(self, request) -> tuple[bool, str | None, str | None, str | None]:
        """Callback'i doğrular. (ok: bool, provider_ref: str|None, message: str|None, order_ref: str|None) döner."""
        raise NotImplementedError

class MockProvider(PaymentProvider):
    def charge(self, *, amount: float, currency: str, order_ref: str) -> ChargeResult:
        # Her zaman başarılı (sahte)
        return ChargeResult(success=True, provider_ref=f"MOCK-{order_ref}", message="OK")
    
    def initiate(self, order, amount, currency, request) -> ChargeResult:
        # Mock için direkt başarı döndür
        return ChargeResult(success=True, provider_ref=f"MOCK-{order.id}", message="Mock ödeme başarılı")
    
    def verify_callback(self, request) -> tuple[bool, str | None, str | None, str | None]:
        # Mock için callback kullanılmaz
        return True, None, "Mock callback", None

class IyzicoProvider(PaymentProvider):
    def charge(self, *, amount: float, currency: str, order_ref: str) -> ChargeResult:
        # Gelecek entegrasyon için yer tutucu
        raise NotImplementedError("Iyzico sandbox entegrasyonu henüz uygulanmadı.")
    
    def initiate(self, order, amount, currency, request) -> ChargeResult:
        # İyzico için gerekli ayarları kontrol et
        api_key = getattr(settings, 'IYZICO_API_KEY', '')
        secret = getattr(settings, 'IYZICO_SECRET', '')
        base_url = getattr(settings, 'IYZICO_BASE_URL', '')
        
        if not all([api_key, secret, base_url]):
            return ChargeResult(
                success=False, 
                message="İyzico konfigürasyonu eksik. API_KEY, SECRET ve BASE_URL gerekli."
            )
        
        # İyzico için auto-submit form oluştur
        form_html = self._generate_iyzico_form(order, amount, currency, request)
        
        return ChargeResult(
            success=True,
            requires_redirect=True,
            form_html=form_html,
            provider_ref=f"IYZICO-{order.id}"
        )
    
    def verify_callback(self, request) -> tuple[bool, str | None, str | None, str | None]:
        # İyzico callback imza doğrulaması
        try:
            # Konfigürasyon kontrolü
            api_key = getattr(settings, 'IYZICO_API_KEY', '')
            secret = getattr(settings, 'IYZICO_SECRET', '')
        except Exception as e:
            # Hata durumunda logla veya varsayılan değer ata
            api_key = ''
            secret = ''
        conversation_id = request.POST.get('conversationId')
        if not all([api_key, secret]):
            return False, None, "İyzico konfigürasyonu eksik", conversation_id

        # İyzico'dan gelen POST verilerini al
        status = request.POST.get('status')
        payment_id = request.POST.get('paymentId')
        provided_hash = request.POST.get('hash')
        # Zorunlu alan kontrolü
        if not all([status, payment_id, conversation_id, provided_hash]):
            return False, None, "Zorunlu alanlar eksik", conversation_id

        # Basit imza doğrulaması (örnek)
        data_to_sign = f"{payment_id}{conversation_id}{status}"
        expected_hash = hmac.new(secret.encode(), data_to_sign.encode(), hashlib.sha256).hexdigest()
        if provided_hash != expected_hash:
            return False, None, "İmza geçersiz", conversation_id

        if status == 'success':
            return True, payment_id, "İyzico ödeme başarılı", conversation_id
        else:
            return False, None, "Ödeme başarısız", conversation_id


def get_provider(settings):
    """Ayarlar üzerinden aktif sağlayıcıyı seç."""
    name = getattr(settings, 'PAYMENT_PROVIDER', 'mock').lower()
    if name == 'iyzico':
        return IyzicoProvider(settings)
    if name == 'paytr':
        return PayTRProvider(settings)
    return MockProvider(settings)

    
    def _generate_iyzico_form(self, order, amount, currency, request):
        # İyzico için basit auto-submit form (gerçek entegrasyon için API çağrısı gerekir)
        callback_url = request.build_absolute_uri(getattr(settings, 'IYZICO_CALLBACK_URL', '/payments/callback/iyzico/'))
        
        form_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>İyzico'ya Yönlendiriliyor...</title>
        </head>
        <body>
            <div style="text-align: center; padding: 50px;">
                <h3>İyzico ödeme sayfasına yönlendiriliyorsunuz...</h3>
                <p>Lütfen bekleyiniz...</p>
            </div>
            <form id="iyzicoForm" method="POST" action="{getattr(settings, 'IYZICO_BASE_URL', '')}/payment/iyzipos/checkoutform/initialize">
                <input type="hidden" name="locale" value="tr" />
                <input type="hidden" name="conversationId" value="{order.id}" />
                <input type="hidden" name="price" value="{amount}" />
                <input type="hidden" name="paidPrice" value="{amount}" />
                <input type="hidden" name="currency" value="{currency}" />
                <input type="hidden" name="basketId" value="{order.id}" />
                <input type="hidden" name="paymentGroup" value="PRODUCT" />
                <input type="hidden" name="callbackUrl" value="{callback_url}" />
            </form>
            <script>
                document.getElementById('iyzicoForm').submit();
            </script>
        </body>
        </html>
        """
        return form_html

class PayTRProvider(PaymentProvider):
    def charge(self, *, amount: float, currency: str, order_ref: str) -> ChargeResult:
        # Gelecek entegrasyon için yer tutucu
        raise NotImplementedError("PayTR sandbox entegrasyonu henüz uygulanmadı.")
    
    def initiate(self, order, amount, currency, request) -> ChargeResult:
        # PayTR için gerekli ayarları kontrol et
        merchant_id = getattr(settings, 'PAYTR_MERCHANT_ID', '')
        merchant_key = getattr(settings, 'PAYTR_MERCHANT_KEY', '')
        merchant_salt = getattr(settings, 'PAYTR_MERCHANT_SALT', '')
        base_url = getattr(settings, 'PAYTR_BASE_URL', '')
        
        if not all([merchant_id, merchant_key, merchant_salt, base_url]):
            return ChargeResult(
                success=False, 
                message="PayTR konfigürasyonu eksik. MERCHANT_ID, MERCHANT_KEY, MERCHANT_SALT ve BASE_URL gerekli."
            )
        
        # PayTR için auto-submit form oluştur
        form_html = self._generate_paytr_form(order, amount, currency, request)
        
        return ChargeResult(
            success=True,
            requires_redirect=True,
            form_html=form_html,
            provider_ref=f"PAYTR-{order.id}"
        )
    
    def verify_callback(self, request) -> tuple[bool, str | None, str | None, str | None]:
        # PayTR callback imza doğrulaması
        try:
            # Konfigürasyon kontrolü
            merchant_id = getattr(settings, 'PAYTR_MERCHANT_ID', '')
            merchant_key = getattr(settings, 'PAYTR_MERCHANT_KEY', '')
            merchant_salt = getattr(settings, 'PAYTR_MERCHANT_SALT', '')
            merchant_oid = request.POST.get('merchant_oid')
            if not all([merchant_id, merchant_key, merchant_salt]):
                return False, None, "PayTR konfigürasyonu eksik", merchant_oid

            status = request.POST.get('status')
            total_amount = request.POST.get('total_amount')
            hash_value = request.POST.get('hash')
            
            # Zorunlu alan kontrolü
            if not all([merchant_oid, status, total_amount, hash_value]):
                return False, None, "Zorunlu alanlar eksik", merchant_oid
            
            # İmza doğrulaması
            calculated_hash = hashlib.md5(f"{merchant_oid}{merchant_salt}{status}{total_amount}".encode()).hexdigest()
            
            if hash_value == calculated_hash and status == 'success':
                return True, merchant_oid, "PayTR ödeme başarılı", merchant_oid
            else:
                # İmza hatalı ise spesifik bir mesaj döndür
                if hash_value != calculated_hash:
                    return False, None, "İmza geçersiz", merchant_oid
                return False, None, "Ödeme başarısız", merchant_oid
        except Exception as e:
            return False, None, f"PayTR callback hatası: {str(e)}", None
    
    def _generate_paytr_form(self, order, amount, currency, request):
        """PayTR için basit auto-submit form (örnek/sandbox)."""
        merchant_id = getattr(settings, 'PAYTR_MERCHANT_ID', '')
        callback_url = request.build_absolute_uri(getattr(settings, 'PAYTR_CALLBACK_URL', '/payments/callback/paytr/'))
        base_url = getattr(settings, 'PAYTR_BASE_URL', '')
        user_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        amount_kurus = int(round(float(amount) * 100))
        form_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>PayTR'ye Yönlendiriliyor...</title></head>
        <body>
          <div style="text-align:center;padding:50px;">
            <h3>PayTR ödeme sayfasına yönlendiriliyorsunuz...</h3>
            <p>Lütfen bekleyiniz...</p>
          </div>
          <form id="paytrForm" method="POST" action="{base_url}/odeme">
            <input type="hidden" name="merchant_id" value="{merchant_id}" />
            <input type="hidden" name="merchant_oid" value="{order.id}" />
            <input type="hidden" name="user_ip" value="{user_ip}" />
            <input type="hidden" name="payment_amount" value="{amount_kurus}" />
            <input type="hidden" name="currency" value="{currency}" />
            <input type="hidden" name="merchant_ok_url" value="{request.build_absolute_uri(getattr(settings,'PAYMENT_SUCCESS_URL','/'))}" />
            <input type="hidden" name="merchant_fail_url" value="{request.build_absolute_uri(getattr(settings,'PAYMENT_FAILURE_URL','/'))}" />
            <input type="hidden" name="callback_url" value="{callback_url}" />
          </form>
          <script>document.getElementById('paytrForm').submit();</script>
        </body>
        </html>
        """
        return form_html
        merchant_key = getattr(settings, 'PAYTR_MERCHANT_KEY', '')
        merchant_salt = getattr(settings, 'PAYTR_MERCHANT_SALT', '')
        callback_url = request.build_absolute_uri(getattr(settings, 'PAYTR_CALLBACK_URL', '/payments/callback/paytr/'))
        
        # PayTR hash hesaplama
        merchant_oid = str(order.id)
        email = order.email or 'test@example.com'
        payment_amount = int(amount * 100)  # PayTR kuruş cinsinden bekler
        
        hash_str = f"{merchant_id}{merchant_oid}{email}{payment_amount}{callback_url}{merchant_salt}"
        paytr_token = hashlib.md5(hash_str.encode()).hexdigest()
        
        form_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>PayTR'ye Yönlendiriliyor...</title>
        </head>
        <body>
            <div style="text-align: center; padding: 50px;">
                <h3>PayTR ödeme sayfasına yönlendiriliyorsunuz...</h3>
                <p>Lütfen bekleyiniz...</p>
            </div>
            <form id="paytrForm" method="POST" action="{getattr(settings, 'PAYTR_BASE_URL', '')}/odeme/api/get-token">
                <input type="hidden" name="merchant_id" value="{merchant_id}" />
                <input type="hidden" name="merchant_oid" value="{merchant_oid}" />
                <input type="hidden" name="email" value="{email}" />
                <input type="hidden" name="payment_amount" value="{payment_amount}" />
                <input type="hidden" name="merchant_ok_url" value="{callback_url}" />
                <input type="hidden" name="merchant_fail_url" value="{callback_url}" />
                <input type="hidden" name="paytr_token" value="{paytr_token}" />
            </form>
            <script>
                document.getElementById('paytrForm').submit();
            </script>
        </body>
        </html>
        """
        return form_html

# Sağlayıcı örneklerini testlerde kolayca mock'layabilmek için hafif bir cache kullanılır
_provider_cache: dict[str, PaymentProvider] = {}

def get_provider(settings=None) -> PaymentProvider:
    """Aktif ödeme sağlayıcısını döndür.
    - settings None ise django.conf.settings kullanılır.
    - settings bir dict ise 'PAYMENT_PROVIDER' anahtarına bakılır; yoksa django settings kullanılır.
    - Aynı sağlayıcı adı için tekil bir örnek (singleton benzeri) döndürülür.
    """
    from django.conf import settings as dj_settings

    provider_name = None
    if isinstance(settings, dict):
        provider_name = settings.get('PAYMENT_PROVIDER')
        effective_settings = dj_settings
    elif settings is None:
        effective_settings = dj_settings
    else:
        effective_settings = settings

    name = (provider_name or getattr(effective_settings, "PAYMENT_PROVIDER", "mock") or "mock").lower()

    if name in _provider_cache:
        return _provider_cache[name]

    if name == "iyzico":
        instance = IyzicoProvider(effective_settings)
    elif name == "paytr":
        instance = PayTRProvider(effective_settings)
    else:
        instance = MockProvider(effective_settings)

    _provider_cache[name] = instance
    return instance