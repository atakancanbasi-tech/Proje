from django.shortcuts import render, get_object_or_404, redirect
from ..models import Product, Order, OrderItem, Review
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from ..forms import ReviewForm
from django.views.decorators.http import require_http_methods
from django.urls import reverse_lazy
from django.conf import settings
import hmac, hashlib

# Sipariş işlemleri

def my_orders(request):
    """Kullanıcının siparişlerini listeler"""
    if not request.user.is_authenticated:
        messages.info(request, 'Siparişlerinizi görmek için giriş yapın.')
        return redirect('accounts:login')
    
    orders = Order.objects.filter(user=request.user).prefetch_related(
        'orderitem_set__product'
    ).only(
        'id', 'status', 'total', 'created_at'
    ).order_by('-created_at')
    return render(request, 'shop/my_orders.html', {'orders': orders})


def order_detail(request, order_id):
    """Sipariş detayını gösterir"""
    order = get_object_or_404(
        Order.objects.prefetch_related(
            'orderitem_set__product__category'
        ).select_related('user'), 
        id=order_id
    )
    
    # Kullanıcı kontrolü
    if request.user.is_authenticated:
        if order.user != request.user:
            messages.error(request, 'Bu siparişi görme yetkiniz yok.')
            return redirect('shop:my_orders')
    else:
        # Anonim kullanıcı için e-posta kontrolü
        if not request.session.get(f'order_{order_id}_email') == order.email:
            messages.error(request, 'Bu siparişi görme yetkiniz yok.')
            return redirect('shop:product_list')
    
    return render(request, 'shop/order_detail.html', {'order': order})


def track_order(request):
    """Kargo takip sayfası"""
    order = None
    error_message = None
    
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        email = request.POST.get('email')
        
        try:
            if order_id and email:
                order = Order.objects.get(id=order_id, email=email)
            else:
                error_message = 'Lütfen sipariş numarası ve e-posta adresinizi girin.'
        except Order.DoesNotExist:
            error_message = 'Sipariş bulunamadı. Lütfen bilgilerinizi kontrol edin.'
        except Exception as e:
            error_message = 'Bir hata oluştu. Lütfen tekrar deneyin.'
    
    return render(request, 'shop/track_order.html', {
        'order': order,
        'error_message': error_message
    })


# Yorum sistemi

def add_review(request, product_id):
    """Ürün için yorum ekleme"""
    if not request.user.is_authenticated:
        messages.error(request, 'Yorum yapabilmek için giriş yapmalısınız.')
        return redirect('accounts:login')
    
    product = get_object_or_404(Product, id=product_id)
    
    # Kullanıcının bu ürünü satın alıp almadığını kontrol et
    has_purchased = OrderItem.objects.filter(
        order__user=request.user,
        product=product,
        order__status='paid'
    ).exists()
    
    if not has_purchased:
        messages.error(request, 'Bu ürün için yorum yapabilmek için önce satın almanız gerekir.')
        return redirect('shop:product_detail', pk=product_id)
    
    # Daha önce yorum yapmış mı kontrol et
    existing_review = Review.objects.filter(user=request.user, product=product).first()
    if existing_review:
        messages.info(request, 'Bu ürün için zaten yorum yapmışsınız. Yorumunuzu düzenleyebilirsiniz.')
        return redirect('shop:edit_review', product_id=product_id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.product = product
            review.is_verified_purchase = True
            review.save()
            messages.success(request, 'Yorumunuz başarıyla eklendi!')
            return redirect('shop:product_detail', pk=product_id)
    else:
        form = ReviewForm()
    
    return render(request, 'shop/add_review.html', {
        'form': form,
        'product': product
    })


def edit_review(request, product_id):
    """Kullanıcının yorumunu düzenleme"""
    if not request.user.is_authenticated:
        messages.error(request, 'Bu sayfaya erişim için giriş yapmalısınız.')
        return redirect('accounts:login')
    
    product = get_object_or_404(Product, id=product_id)
    review = get_object_or_404(Review, user=request.user, product=product)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, 'Yorumunuz başarıyla güncellendi!')
            return redirect('product_detail', pk=product_id)
    else:
        form = ReviewForm(instance=review)
    
    return render(request, 'shop/edit_review.html', {
        'form': form,
        'product': product,
        'review': review
    })


def delete_review(request, product_id):
    """Kullanıcının yorumunu silme"""
    if not request.user.is_authenticated:
        messages.error(request, 'Yorum silebilmek için giriş yapmalısınız.')
        return redirect('accounts:login')
    
    product = get_object_or_404(Product, id=product_id)
    review = get_object_or_404(Review, user=request.user, product=product)
    
    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Yorumunuz başarıyla silindi.')
        return redirect('product_detail', pk=product_id)
    
    return render(request, 'shop/delete_review.html', {
        'product': product,
        'review': review
    })


def _receipt_signature(order) -> str:
    """
    Linke 'sig' parametresiyle erişim için HMAC imzası.
    paid_at varsa onu, yoksa created/created_at ya da sadece id kullanır.
    Migrasyon gerekmez.
    """
    ts = getattr(order, "paid_at", None) or getattr(order, "created", None) or getattr(order, "created_at", None)
    base = f"{order.id}|{int(ts.timestamp()) if ts else order.id}"
    return hmac.new(settings.SECRET_KEY.encode(), base.encode(), hashlib.sha256).hexdigest()[:32]


@login_required(login_url=reverse_lazy('security:login'))
def order_receipt(request, pk: int):
    """
    Yazdırılabilir sipariş fişi (HTML).
    Erişim koşulu: (1) personel ya da siparişin sahibi kullanıcı, veya
                   (2) geçerli ?sig=... imzası (opsiyonel linkler için).
    """
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('orderitem_set__product'),
        pk=pk
    )
    
    sig = request.GET.get("sig")
    is_owner = (getattr(order, "user_id", None) == getattr(request.user, "id", None))
    has_sig = bool(sig and sig == _receipt_signature(order))
    
    if not (request.user.is_staff or is_owner or has_sig):
        return HttpResponseForbidden("Bu fişi görüntüleme izniniz yok.")
    
    # Kalemler: order.items varsa onu, yoksa orderitem_set'i kullan
    items_qs = getattr(order, "items", None)
    items = items_qs.all() if items_qs is not None else order.orderitem_set.all()
    
    # Görsel alanlar: ürün adı, adet, birim fiyat, satır toplamı
    items_data = []
    for it in items:
        product = getattr(it, "product", None)
        name = getattr(product, "name", str(product)) if product else "Ürün"
        qty = getattr(it, "quantity", 1)
        unit_price = (
            getattr(it, "unit_price", None)
            or getattr(it, "price", None)
            or (getattr(product, "price", 0) if product else 0)
        )
        line_total = (
            getattr(it, "total_price", None)
            or getattr(it, "total", None)
            or (unit_price * qty)
        )
        items_data.append({"name": name, "qty": qty, "unit_price": unit_price, "line_total": line_total})
    
    subtotal = sum(i["line_total"] for i in items_data)
    shipping_fee = getattr(order, "shipping_fee", 0) or 0
    discount = getattr(order, "discount_amount", 0) or 0
    grand_total = getattr(order, "total", None)
    if grand_total is None:
        grand_total = subtotal + shipping_fee - discount
    
    ctx = {
        "order": order,
        "items": items_data,
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "discount": discount,
        "grand_total": grand_total,
    }
    return render(request, "shop/order_receipt.html", ctx)