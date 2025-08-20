# payments/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from shop.models import Order
from .provider import get_provider


def _csrf_post_ratelimited(view):
    # Sıra garantisi: önce require_POST, sonra ratelimit, en sonda csrf_exempt
    return csrf_exempt(ratelimit(key="ip", rate="10/m", block=True)(require_POST(view)))


@_csrf_post_ratelimited
def iyzico_callback(request):
    """İyzico callback handler (idempotent)"""
    provider = get_provider(settings)
    
    # Callback'i doğrula ve order_ref'i de al
    ok, provider_ref, message, order_ref = provider.verify_callback(request)
    if not ok:
        failure_url = getattr(settings, 'PAYMENT_FAILURE_URL', '/')
        return HttpResponseRedirect(failure_url)

    # order_ref (conversationId) ile siparişi bul ve kilitle
    try:
        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), id=order_ref)
            
            # Idempotency: zaten işlendi mi?
            if order.status == 'paid' or (order.payment_ref and order.payment_ref == provider_ref):
                # No-op
                return HttpResponse("ok")
            
            # Güncelle
            order.status = 'paid'
            order.payment_provider = 'iyzico'
            if hasattr(order, "payment_ref"):
                order.payment_ref = provider_ref
            order.paid_at = timezone.now()
            order.save()
            
            # Stok düş
            for item in order.items.all():
                product = item.product
                if product.stock >= item.quantity:
                    product.stock -= item.quantity
                    product.save()
            
            # E-posta gönder
            _send_order_confirmation_email(order)
            
            # Başarı sayfasına yönlendir
            success_url = getattr(settings, 'PAYMENT_SUCCESS_URL', '/')
            return HttpResponseRedirect(success_url)
    except Order.DoesNotExist:
        failure_url = getattr(settings, 'PAYMENT_FAILURE_URL', '/')
        return HttpResponseRedirect(failure_url)


@_csrf_post_ratelimited
def paytr_callback(request):
    """PayTR callback handler (idempotent)"""
    provider = get_provider(settings)
    
    # Callback'i doğrula ve order_ref'i al (merchant_oid)
    ok, provider_ref, message, order_ref = provider.verify_callback(request)
    if not ok:
        return HttpResponse("FAIL")

    try:
        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), id=order_ref)
            
            # Idempotency kontrolü
            if order.status == 'paid' or (order.payment_ref and order.payment_ref == provider_ref):
                return HttpResponse("OK")
            
            order.status = 'paid'
            order.payment_provider = 'paytr'
            order.payment_ref = provider_ref
            order.paid_at = timezone.now()
            order.save()
            
            # Stok düş
            for item in order.items.all():
                product = item.product
                if product.stock >= item.quantity:
                    product.stock -= item.quantity
                    product.save()
            
            # E-posta gönder
            _send_order_confirmation_email(order)
            
            return HttpResponse("OK")
    except Order.DoesNotExist:
        return HttpResponse("FAIL")


def _send_order_confirmation_email(order):
    """Sipariş onay e-postası gönder"""
    try:
        subject = f'Sipariş Onayı - #{order.id}'
        
        # HTML e-posta içeriği
        html_content = render_to_string('shop/emails/order_confirmation.html', {
            'order': order,
            'site_name': 'Satış Sitesi'
        })
        
        # Text e-posta içeriği
        text_content = f"""
        Merhaba {order.fullname},
        
        Siparişiniz başarıyla alınmıştır.
        
        Sipariş No: #{order.id}
        Toplam: {order.total} TL
        
        Teşekkürler!
        """
        
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.email],
            html_message=html_content,
            fail_silently=True
        )
    except Exception as e:
        # E-posta gönderimi başarısız olsa bile sipariş işlemi devam etsin
        print(f"E-posta gönderimi hatası: {e}")