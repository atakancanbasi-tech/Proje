from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from shop.models import Order


@login_required
@require_POST
@ratelimit(key="user", rate="5/m", method=["POST"], block=True)
def cancel_order(request, order_id: int):
    """
    Sadece 'received' durumundaki siparişi iptal eder.
    Sipariş sahibi veya staff kullanıcı iptal edebilir.
    İptalde stok geri yüklenir. İdempotent: yeniden iptal denemesi
    stokları ikinci kez arttırmaz.
    """
    order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
    
    if not (request.user.is_staff or order.user_id == request.user.id):
        return HttpResponseForbidden("Bu siparişi iptal etme yetkiniz yok.")
    
    # Aynı anda iki iptal isteğine karşı güvenli ol
    with transaction.atomic():
        order.refresh_from_db()
        
        if order.status == "cancelled":
            # İdempotent: ikinci çağrıda stok dokunma, nazik cevap ver
            messages.info(request, "Sipariş zaten iptal edilmiş.")
            return HttpResponse("OK")
        
        if order.status != "received":
            return HttpResponse(status=409)  # state conflict
        
        # Stokları geri yükle
        for item in order.items.select_related("product").all():
            product = item.product
            product.stock = product.stock + item.quantity
            product.save(update_fields=["stock"])
        
        # Durumu güncelle
        order.status = "cancelled"
        order.save(update_fields=["status"])
        
        messages.success(request, "Siparişiniz iptal edildi.")
        return HttpResponse("OK")