from django.shortcuts import render, get_object_or_404, redirect
from ..models import Product, Wishlist, StockAlert
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

# Hesap ile ilgili view'lar

def wishlist_view(request):
    """Kullanıcının istek listesini gösterir"""
    if not request.user.is_authenticated:
        messages.info(request, 'İstek listenizi görmek için giriş yapın.')
        return redirect('accounts:login')
    
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related(
        'product__category'
    ).only(
        'id', 'product__id', 'product__name', 'product__price', 
        'product__image', 'product__category__name', 'created_at'
    )
    
    return render(request, 'shop/wishlist.html', {
        'wishlist_items': wishlist_items
    })


def add_to_wishlist(request, product_id):
    """Ürünü istek listesine ekler"""
    if not request.user.is_authenticated:
        messages.info(request, 'İstek listesine eklemek için giriş yapın.')
        return redirect('accounts:login')
    
    product = get_object_or_404(Product, id=product_id)
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if created:
        messages.success(request, f'{product.name} istek listenize eklendi.')
    else:
        messages.info(request, f'{product.name} zaten istek listenizde.')
    
    return redirect('shop:product_detail', pk=product_id)


def remove_from_wishlist(request, product_id):
    """Ürünü istek listesinden çıkarır"""
    if not request.user.is_authenticated:
        messages.info(request, 'Giriş yapın.')
        return redirect('accounts:login')
    
    product = get_object_or_404(Product, id=product_id)
    
    try:
        wishlist_item = Wishlist.objects.get(user=request.user, product=product)
        wishlist_item.delete()
        messages.success(request, f'{product.name} istek listenizden çıkarıldı.')
    except Wishlist.DoesNotExist:
        messages.error(request, 'Bu ürün istek listenizde bulunmuyor.')
    
    # Referrer kontrolü - nereden geldiğini kontrol et
    referer = request.META.get('HTTP_REFERER')
    if referer and 'wishlist' in referer:
        return redirect('shop:wishlist')
    else:
        return redirect('shop:product_detail', pk=product_id)


# Stok Uyarısı Sistemi

def create_stock_alert(request, product_id):
    """Stok uyarısı oluştur"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Stok uyarısı oluşturmak için giriş yapmalısınız.'
        })
    
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        email = request.POST.get('email', request.user.email)
        threshold = int(request.POST.get('threshold', 1))
        
        # Zaten var mı kontrol et
        existing_alert = StockAlert.objects.filter(
            user=request.user,
            product=product,
            status='active'
        ).first()
        
        if existing_alert:
            return JsonResponse({
                'success': False,
                'message': 'Bu ürün için zaten aktif bir stok uyarınız bulunuyor.'
            })
        
        # Yeni stok uyarısı oluştur
        stock_alert = StockAlert.objects.create(
            user=request.user,
            product=product,
            email=email,
            threshold=threshold
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{product.name} için stok uyarısı oluşturuldu. Ürün stokta olduğunda e-posta ile bilgilendirileceksiniz.'
        })
    
    return JsonResponse({'success': False, 'message': 'Geçersiz istek.'})


def cancel_stock_alert(request, product_id):
    """Stok uyarısını iptal et"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Giriş yapmalısınız.'
        })
    
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        
        try:
            stock_alert = StockAlert.objects.get(
                user=request.user,
                product=product,
                status='active'
            )
            stock_alert.status = 'cancelled'
            stock_alert.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Stok uyarısı iptal edildi.'
            })
        except StockAlert.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Aktif stok uyarısı bulunamadı.'
            })
    
    return JsonResponse({'success': False, 'message': 'Geçersiz istek.'})


def my_stock_alerts(request):
    """Kullanıcının stok uyarıları"""
    if not request.user.is_authenticated:
        messages.error(request, 'Stok uyarılarınızı görmek için giriş yapmalısınız.')
        return redirect('accounts:login')
    
    alerts = StockAlert.objects.filter(user=request.user).select_related('product')
    
    context = {
        'alerts': alerts
    }
    
    return render(request, 'shop/stock_alerts.html', context)


def check_stock_alerts():
    """Stok uyarılarını kontrol et ve bildirim gönder (cron job için)"""
    active_alerts = StockAlert.objects.filter(status='active').select_related('product', 'user')
    
    sent_count = 0
    for alert in active_alerts:
        if alert.product.stock >= alert.threshold:
            if alert.send_notification():
                sent_count += 1
    
    return sent_count