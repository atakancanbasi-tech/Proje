from django.shortcuts import render, get_object_or_404, redirect
from .models import Product, Category, Order, OrderItem, Review, Wishlist, Coupon, CouponUsage, StockAlert, ProductAttribute, ProductAttributeValue, ProductVariant, ProductVariantAttribute
from .cart import Cart
from .forms import OrderForm, ReviewForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count, Min, Max
from django.http import JsonResponse
from django.db import models
from .utils import send_order_confirmation_email, calculate_shipping_options, calculate_order_totals
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json

# Ürün listesi

def product_list(request):
    # Ana sayfa kontrolü
    is_homepage = not any(request.GET.get(param) for param in ['q', 'category', 'min_price', 'max_price', 'in_stock', 'min_rating', 'sort'])
    
    if is_homepage:
        # Ana sayfa için özel veriler
        try:
            # Öne çıkan ürünler (yüksek puanlı)
            featured_products = Product.objects.select_related('category').only(
                'id', 'name', 'price', 'stock', 'image', 'category__name'
            ).filter(
                stock__gt=0
            ).annotate(
                avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
                review_count=Count('reviews', filter=Q(reviews__is_approved=True))
            ).filter(avg_rating__gte=4.0).order_by('-avg_rating', '-review_count')[:6]
            
            # En çok satan ürünler
            bestsellers = Product.objects.select_related('category').only(
                'id', 'name', 'price', 'stock', 'image', 'category__name'
            ).filter(
                stock__gt=0
            ).annotate(
                order_count=Count('orderitem')
            ).order_by('-order_count')[:6]
            
            # Yeni ürünler
            new_products = Product.objects.select_related('category').only(
                'id', 'name', 'price', 'stock', 'image', 'category__name'
            ).filter(
                stock__gt=0
            ).order_by('-id')[:6]
            
            # Kategoriler (ürün sayısı ile)
            categories_with_count = Category.objects.annotate(
                product_count=Count('products', filter=Q(products__stock__gt=0))
            ).filter(product_count__gt=0).order_by('-product_count')[:8]
            
        except Exception:
            # Hata durumunda basit veriler
            featured_products = Product.objects.filter(stock__gt=0)[:6]
            bestsellers = Product.objects.filter(stock__gt=0)[:6]
            new_products = Product.objects.filter(stock__gt=0).order_by('-id')[:6]
            categories_with_count = Category.objects.all()[:8]
        
        context = {
            'is_homepage': True,
            'featured_products': featured_products,
            'bestsellers': bestsellers,
            'new_products': new_products,
            'categories_with_count': categories_with_count,
        }
        return render(request, 'shop/product_list.html', context)
    
    # Ürün listesi sayfası için normal mantık
    products = Product.objects.select_related('category').only(
        'id', 'name', 'price', 'stock', 'image', 'category__name'
    ).filter(stock__gt=0)
    categories = Category.objects.only('id', 'name').all()
    
    # Arama
    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Kategori filtresi
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Sayfalama
    paginator = Paginator(products.order_by('name'), 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
    }
    return render(request, 'shop/product_list.html', context)
    
    # Filtreleme sayfası için mevcut kod
    products = Product.objects.select_related('category').all()
    
    # Arama
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    
    # Kategori filtresi
    category_id = request.GET.get('category', '').strip()
    if category_id.isdigit():
        products = products.filter(category_id=int(category_id))
    
    # Fiyat aralığı filtresi
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Stok durumu filtresi
    in_stock = request.GET.get('in_stock')
    if in_stock == 'true':
        products = products.filter(stock__gt=0)
    elif in_stock == 'false':
        products = products.filter(stock=0)
    
    # Puan filtresi
    min_rating = request.GET.get('min_rating', '').strip()
    if min_rating:
        try:
            rating = int(min_rating)
            if 1 <= rating <= 5:
                # Ortalama puanı hesapla ve filtrele
                from django.db.models import Avg
                products = products.annotate(
                    avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
                ).filter(avg_rating__gte=rating)
        except ValueError:
            pass
    
    # Sıralama
    sort_by = request.GET.get('sort', 'name')
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'rating':
        from django.db.models import Avg
        products = products.annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
        ).order_by('-avg_rating', 'name')
    elif sort_by == 'newest':
        products = products.order_by('-id')
    elif sort_by == 'oldest':
        products = products.order_by('id')
    else:  # name (default)
        products = products.order_by('name')
    
    categories = Category.objects.all()
    
    # Fiyat aralığı için min/max değerleri
    price_range = Product.objects.aggregate(
        min_price=models.Min('price'),
        max_price=models.Max('price')
    )
    
    context = {
        'is_homepage': False,
        'products': products,
        'categories': categories,
        'q': q,
        'selected_category': int(category_id) if category_id.isdigit() else '',
        'min_price': min_price,
        'max_price': max_price,
        'in_stock': in_stock,
        'min_rating': min_rating,
        'sort_by': sort_by,
        'price_range': price_range,
    }
    return render(request, 'shop/product_list.html', context)

# Ürün detayı

def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related(
            'reviews__user',
            'variants__attributes__attribute',
            'stock_alerts'
        ), 
        pk=pk
    )
    reviews = product.reviews.filter(is_approved=True).select_related('user')
    
    # Kullanıcının bu ürün için yorumu var mı kontrol et
    user_review = None
    can_review = False
    has_purchased = False
    is_in_wishlist = False
    
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        # Kullanıcının bu ürünü satın alıp almadığını kontrol et
        has_purchased = OrderItem.objects.filter(
            order__user=request.user,
            product=product,
            order__status='paid'
        ).exists()
        can_review = has_purchased and not user_review
        
        # Kullanıcının istek listesinde olup olmadığını kontrol et
        is_in_wishlist = Wishlist.objects.filter(
            user=request.user,
            product=product
        ).exists()
        
        # Kullanıcının bu ürün için aktif stok uyarısı var mı kontrol et
        has_active_stock_alert = StockAlert.objects.filter(
            user=request.user,
            product=product,
            status='active'
        ).exists()
    else:
        has_active_stock_alert = False
    
    context = {
        'product': product,
        'reviews': reviews,
        'user_review': user_review,
        'can_review': can_review,
        'has_purchased': has_purchased,
        'is_in_wishlist': is_in_wishlist,
        'has_active_stock_alert': has_active_stock_alert,
    }
    return render(request, 'shop/product_detail.html', context)

# Sepet işlemleri

def add_to_cart(request, pk):
    cart = Cart(request)
    product = get_object_or_404(Product, pk=pk)
    # Stok kontrolü: sepetteki mevcut miktarı aşmasına izin verme
    current_qty = cart.get_quantity(product)
    if product.stock <= current_qty:
        messages.warning(request, f'{product.name} için stok sınırına ulaştınız.')
    else:
        cart.add(product)
        messages.success(request, f'{product.name} sepete eklendi.')
    return redirect('shop:cart_detail')


def decrement_from_cart(request, pk):
    cart = Cart(request)
    product = get_object_or_404(Product, pk=pk)
    cart.decrement(product)
    messages.info(request, f'{product.name} adedi azaltıldı.')
    return redirect('shop:view_cart')


def update_cart_quantity(request, pk):
    if request.method != 'POST':
        return redirect('shop:cart_detail')
    cart = Cart(request)
    product = get_object_or_404(Product, pk=pk)
    try:
        qty = int(request.POST.get('quantity', '1'))
    except ValueError:
        qty = 1
    if qty < 0:
        qty = 0
    # Stok aşımı engelle
    if qty > product.stock:
        qty = product.stock
        messages.warning(request, f'{product.name} için maksimum {product.stock} adet eklenebilir.')
    cart.set(product, qty)
    messages.success(request, f'{product.name} miktarı {qty} olarak güncellendi.')
    return redirect('shop:view_cart')


def view_cart(request):
    cart = Cart(request)
    return render(request, 'shop/cart.html', {'cart': cart})


def remove_from_cart(request, pk):
    cart = Cart(request)
    product = get_object_or_404(Product, pk=pk)
    cart.remove(product)
    messages.info(request, f'{product.name} sepetten silindi.')
    return redirect('shop:view_cart')


@require_http_methods(["GET", "POST"])
def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.info(request, 'Sepetiniz boş, önce ürün ekleyin.')
        return redirect('shop:product_list')

    cart_total = Decimal(cart.get_total_price())
    cart_items = [{
        'price': Decimal(str(item['price'])),
        'quantity': item['quantity']
    } for item in cart]

    # Giriş yapmış kullanıcı için başlangıç verileri
    initial_data = {}
    if request.user.is_authenticated:
        initial_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        }

    if request.method == 'POST':
        form = OrderForm(request.POST, cart_total=cart_total)
        if form.is_valid():
            # Stok yeniden doğrula
            for item in cart:
                product = item['product']
                qty = item['quantity']
                if qty > product.stock:
                    messages.error(request, f'{product.name} için kalan stok {product.stock}. Miktarı güncelledik.')
                    cart.set(product, product.stock)
                    return redirect('shop:cart_detail')

            # Sipariş toplamlarını hesapla
            shipping_company_id = form.cleaned_data['shipping_company'].id if form.cleaned_data['shipping_company'] else None
            payment_method_id = form.cleaned_data['payment_method'].id if form.cleaned_data['payment_method'] else None
            
            totals = calculate_order_totals(cart_items, shipping_company_id, payment_method_id)

            # Kupon kontrolü ve uygulaması
            coupon = None
            discount_amount = Decimal('0')
            if 'coupon_id' in request.session:
                try:
                    coupon = Coupon.objects.get(id=request.session['coupon_id'])
                    is_valid, message = coupon.is_valid(user=request.user, order_amount=totals['total_amount'])
                    if is_valid:
                        discount_amount = coupon.calculate_discount(totals['total_amount'])
                        totals['total_amount'] -= discount_amount
                    else:
                        messages.warning(request, f'Kupon geçersiz: {message}')
                        # Session'dan kupon bilgilerini kaldır
                        del request.session['coupon_id']
                        if 'coupon_code' in request.session:
                            del request.session['coupon_code']
                        if 'discount_amount' in request.session:
                            del request.session['discount_amount']
                        coupon = None
                except Coupon.DoesNotExist:
                    coupon = None

            # Sipariş oluştur
            order = form.save(commit=False)
            order.user = request.user if request.user.is_authenticated else None
            order.subtotal = totals['subtotal']
            order.shipping_cost = totals['shipping_cost']
            order.processing_fee = totals['processing_fee']
            order.total = totals.get('total') or totals.get('total_amount')
            order.coupon = coupon
            order.discount_amount = discount_amount
            order.status = 'received'
            order.save()

            # Kalemleri oluştur ve stok düş
            for item in cart:
                product = item['product']
                qty = item['quantity']
                price = item['product'].price
                OrderItem.objects.create(order=order, product=product, quantity=qty, price=price)
                product.stock = max(0, product.stock - qty)
                product.save(update_fields=['stock'])

            # Kupon kullanım kaydı oluştur
            if coupon and request.user.is_authenticated:
                CouponUsage.objects.create(
                    coupon=coupon,
                    user=request.user,
                    order=order,
                    discount_amount=discount_amount
                )

            # Sipariş toplamlarını yeniden hesapla ve kaydet
            order.calculate_totals()
            order.save()

            # Session'dan kupon bilgilerini temizle
            if 'coupon_id' in request.session:
                del request.session['coupon_id']
            if 'coupon_code' in request.session:
                del request.session['coupon_code']
            if 'discount_amount' in request.session:
                del request.session['discount_amount']

            # Sepeti temizle
            cart.clear()
            
            # Sipariş onayı e-postası gönder
            email_sent = send_order_confirmation_email(order)
            if email_sent:
                messages.success(request, f'Siparişiniz oluşturuldu. Sipariş No: {order.id}. Onay e-postası gönderildi.')
            else:
                messages.success(request, f'Siparişiniz oluşturuldu. Sipariş No: {order.id}')
                messages.warning(request, 'E-posta gönderilemedi, ancak siparişiniz başarıyla alındı.')
            
            return redirect('checkout_success', order_id=order.id)
    else:
        form = OrderForm(initial=initial_data, cart_total=cart_total)

    # Kargo seçeneklerini hesapla
    shipping_options = calculate_shipping_options(cart_total)

    context = {
        'cart': cart,
        'form': form,
        'shipping_options': shipping_options,
        'cart_total': cart_total
    }
    return render(request, 'shop/checkout.html', context)


def checkout_success(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            'orderitem_set__product__category'
        ).select_related('user'), 
        id=order_id
    )
    return render(request, 'shop/checkout_success.html', {'order': order})


def calculate_checkout_totals(request):
    """AJAX ile kargo ve ödeme seçeneklerine göre toplam hesapla"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            shipping_company_id = data.get('shipping_company_id')
            payment_method_id = data.get('payment_method_id')
            
            cart = Cart(request)
            cart_items = [{
                'price': Decimal(str(item['price'])),
                'quantity': item['quantity']
            } for item in cart]
            
            totals = calculate_order_totals(cart_items, shipping_company_id, payment_method_id)
            
            return JsonResponse({
                'success': True,
                'subtotal': float(totals['subtotal']),
                'shipping_cost': float(totals['shipping_cost']),
                'processing_fee': float(totals['processing_fee']),
                'total': float(totals.get('total', totals.get('total_amount', 0)))
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


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
            return redirect('my_orders')
    else:
        # Anonim kullanıcı için e-posta kontrolü
        if not request.session.get(f'order_{order_id}_email') == order.email:
            messages.error(request, 'Bu siparişi görme yetkiniz yok.')
            return redirect('product_list')
    
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
        return redirect('product_detail', pk=product_id)
    
    # Daha önce yorum yapmış mı kontrol et
    existing_review = Review.objects.filter(user=request.user, product=product).first()
    if existing_review:
        messages.info(request, 'Bu ürün için zaten yorum yapmışsınız. Yorumunuzu düzenleyebilirsiniz.')
        return redirect('edit_review', product_id=product_id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.product = product
            review.is_verified_purchase = True
            review.save()
            messages.success(request, 'Yorumunuz başarıyla eklendi!')
            return redirect('product_detail', pk=product_id)
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
        messages.error(request, 'Bu işlem için giriş yapmalısınız.')
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


def wishlist_view(request):
    """Kullanıcının istek listesini gösterir"""
    if not request.user.is_authenticated:
        messages.info(request, 'İstek listenizi görmek için giriş yapın.')
        return redirect('accounts:login')
    
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related(
        'product__category'
    ).only(
        'id', 'product__id', 'product__name', 'product__price', 
        'product__image', 'product__category__name'
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
    
    return redirect('product_detail', pk=product_id)


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
        return redirect('wishlist')
    else:
        return redirect('product_detail', pk=product_id)


# Kupon Sistemi

def validate_coupon(request):
    """AJAX ile kupon doğrulama"""
    if request.method == 'POST':
        coupon_code = request.POST.get('coupon_code', '').strip().upper()
        
        if not coupon_code:
            return JsonResponse({
                'success': False,
                'message': 'Kupon kodu giriniz.'
            })
        
        try:
            coupon = Coupon.objects.get(code=coupon_code)
            
            # Sepet tutarını al
            cart = Cart(request)
            cart_total = cart.get_total_price()
            
            # Kupon geçerliliğini kontrol et
            is_valid, message = coupon.is_valid(user=request.user, order_amount=cart_total)
            
            if not is_valid:
                return JsonResponse({
                    'success': False,
                    'message': message
                })
            
            # İndirim tutarını hesapla
            discount_amount = coupon.calculate_discount(cart_total)
            
            # Session'a kupon bilgisini kaydet
            request.session['coupon_id'] = coupon.id
            request.session['coupon_code'] = coupon.code
            request.session['discount_amount'] = float(discount_amount)
            
            return JsonResponse({
                'success': True,
                'message': f'Kupon başarıyla uygulandı! {discount_amount} TL indirim.',
                'coupon_code': coupon.code,
                'discount_amount': float(discount_amount),
                'discount_type': coupon.discount_type
            })
            
        except Coupon.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Geçersiz kupon kodu.'
            })
    
    return JsonResponse({'success': False, 'message': 'Geçersiz istek.'})


def remove_coupon(request):
    """Kupon kaldırma"""
    if request.method == 'POST':
        # Session'dan kupon bilgilerini kaldır
        if 'coupon_id' in request.session:
            del request.session['coupon_id']
        if 'coupon_code' in request.session:
            del request.session['coupon_code']
        if 'discount_amount' in request.session:
            del request.session['discount_amount']
        
        return JsonResponse({
            'success': True,
            'message': 'Kupon kaldırıldı.'
        })
    
    return JsonResponse({'success': False, 'message': 'Geçersiz istek.'})


def get_user_coupons(request):
    """Kullanıcının kullanabileceği kuponları listele"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Giriş yapmalısınız.'})
    
    from django.utils import timezone
    now = timezone.now()
    
    # Kullanıcının kullanabileceği kuponları bul
    available_coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_until__gte=now
    ).filter(
        models.Q(valid_users__isnull=True) | models.Q(valid_users=request.user)
    ).distinct()
    
    # Sepet tutarını al
    cart = Cart(request)
    cart_total = cart.get_total_price()
    
    coupon_list = []
    for coupon in available_coupons:
        is_valid, message = coupon.is_valid(user=request.user, order_amount=cart_total)
        if is_valid:
            discount_amount = coupon.calculate_discount(cart_total)
            coupon_list.append({
                'code': coupon.code,
                'name': coupon.name,
                'description': coupon.description,
                'discount_type': coupon.get_discount_type_display(),
                'discount_value': float(coupon.discount_value),
                'discount_amount': float(discount_amount),
                'min_order_amount': float(coupon.min_order_amount) if coupon.min_order_amount else None
            })
    
    return JsonResponse({
        'success': True,
        'coupons': coupon_list
    })


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


@require_http_methods(["GET"])
def get_product_variants(request, product_id):
    """Ürün varyantlarını JSON olarak döndür"""
    try:
        product = get_object_or_404(Product, id=product_id)
        variants = ProductVariant.objects.filter(
            product=product, 
            is_active=True
        ).prefetch_related('attribute_values__attribute_value__attribute')
        
        # Ürün özelliklerini grupla
        attributes = {}
        for variant in variants:
            for variant_attr in variant.attribute_values.all():
                attr = variant_attr.attribute_value.attribute
                attr_value = variant_attr.attribute_value
                
                if attr.name not in attributes:
                    attributes[attr.name] = {
                        'display_name': attr.display_name,
                        'values': []
                    }
                
                value_data = {
                    'id': attr_value.id,
                    'value': attr_value.value,
                    'display_value': attr_value.display_value,
                    'color_code': attr_value.color_code
                }
                
                if value_data not in attributes[attr.name]['values']:
                    attributes[attr.name]['values'].append(value_data)
        
        # Varyant verilerini hazırla
        variants_data = []
        for variant in variants:
            variant_attrs = {}
            for variant_attr in variant.attribute_values.all():
                attr_name = variant_attr.attribute_value.attribute.name
                variant_attrs[attr_name] = variant_attr.attribute_value.id
            
            variants_data.append({
                'id': variant.id,
                'sku': variant.sku,
                'price': float(variant.effective_price),
                'stock': variant.stock,
                'is_in_stock': variant.is_in_stock,
                'image': variant.image.url if variant.image else None,
                'attributes': variant_attrs
            })
        
        return JsonResponse({
            'success': True,
            'attributes': attributes,
            'variants': variants_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["GET"])
def search_autocomplete(request):
    """Arama için otomatik tamamlama önerileri"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    try:
        # Ürün adlarından öneriler
        product_suggestions = Product.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:5]
        
        # Kategori adlarından öneriler
        category_suggestions = Category.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:3]
        
        # Ürün açıklamalarından kelime önerileri
        description_words = []
        products_with_desc = Product.objects.filter(
            description__icontains=query
        ).values_list('description', flat=True)[:3]
        
        for desc in products_with_desc:
            if desc:
                words = desc.split()
                matching_words = [word.strip('.,!?;:') for word in words 
                                if query.lower() in word.lower() and len(word) > 3]
                description_words.extend(matching_words[:2])
        
        # Benzersiz öneriler oluştur
        all_suggestions = list(product_suggestions) + list(category_suggestions) + description_words
        unique_suggestions = []
        seen = set()
        
        for suggestion in all_suggestions:
            if suggestion.lower() not in seen and len(unique_suggestions) < 8:
                unique_suggestions.append(suggestion)
                seen.add(suggestion.lower())
        
        return JsonResponse({
            'suggestions': unique_suggestions
        })
        
    except Exception as e:
        return JsonResponse({
            'suggestions': [],
            'error': str(e)
        })


@require_http_methods(["GET"])
def advanced_search(request):
    """Gelişmiş arama sayfası"""
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    min_rating = request.GET.get('min_rating', '')
    in_stock = request.GET.get('in_stock', '')
    sort_by = request.GET.get('sort', 'relevance')
    
    products = Product.objects.select_related('category').all()
    
    # Arama sorgusu
    if query:
        # Ürün adı, açıklama ve kategori adında arama
        products = products.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Kategori filtresi
    if category_id and category_id.isdigit():
        products = products.filter(category_id=int(category_id))
    
    # Fiyat aralığı
    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass
    
    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Minimum puan
    if min_rating:
        try:
            rating = int(min_rating)
            if 1 <= rating <= 5:
                products = products.annotate(
                    avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
                ).filter(avg_rating__gte=rating)
        except ValueError:
            pass
    
    # Stok durumu
    if in_stock == 'true':
        products = products.filter(stock__gt=0)
    elif in_stock == 'false':
        products = products.filter(stock=0)
    
    # Sıralama
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'rating':
        products = products.annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
        ).order_by('-avg_rating', 'name')
    elif sort_by == 'newest':
        products = products.order_by('-id')
    elif sort_by == 'name':
        products = products.order_by('name')
    else:  # relevance (default)
        if query:
            # Relevance scoring: exact matches first, then partial matches
            products = products.extra(
                select={
                    'relevance': """
                    CASE 
                        WHEN LOWER(shop_product.name) = LOWER(%s) THEN 3
                        WHEN LOWER(shop_product.name) LIKE LOWER(%s) THEN 2
                        WHEN LOWER(shop_product.description) LIKE LOWER(%s) THEN 1
                        ELSE 0
                    END
                    """
                },
                select_params=[query, f'%{query}%', f'%{query}%']
            ).order_by('-relevance', 'name')
        else:
            products = products.order_by('name')
    
    # Sayfalama
    from django.core.paginator import Paginator
    paginator = Paginator(products, 12)  # Sayfa başına 12 ürün
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Kategoriler
    categories = Category.objects.all()
    
    # Fiyat aralığı
    price_range = Product.objects.aggregate(
        min_price=models.Min('price'),
        max_price=models.Max('price')
    )
    
    context = {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'categories': categories,
        'query': query,
        'selected_category': int(category_id) if category_id and category_id.isdigit() else '',
        'min_price': min_price,
        'max_price': max_price,
        'min_rating': min_rating,
        'in_stock': in_stock,
        'sort_by': sort_by,
        'price_range': price_range,
        'total_results': paginator.count,
    }
    
    return render(request, 'shop/advanced_search.html', context)


@require_http_methods(["POST"])
def add_variant_to_cart(request, variant_id):
    """Ürün varyantını sepete ekle"""
    try:
        variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)
        
        if not variant.is_in_stock:
            return JsonResponse({
                'success': False,
                'error': 'Bu varyant stokta yok.'
            })
        
        cart = Cart(request)
        quantity = int(request.POST.get('quantity', 1))
        
        # Sepete varyant ekle (cart.py'da güncelleme gerekebilir)
        cart.add(variant.product, quantity=quantity, variant_id=variant.id)
        
        return JsonResponse({
            'success': True,
            'message': f'{variant.product.name} ({variant.get_attribute_display()}) sepete eklendi.',
            'cart_count': len(cart)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["GET"])
def get_variant_details(request, variant_id):
    """Varyant detaylarını JSON olarak döndür"""
    try:
        variant = get_object_or_404(
            ProductVariant.objects.prefetch_related(
                'attribute_values__attribute_value__attribute'
            ), 
            id=variant_id, 
            is_active=True
        )
        
        return JsonResponse({
            'success': True,
            'variant': {
                'id': variant.id,
                'sku': variant.sku,
                'price': float(variant.effective_price),
                'stock': variant.stock,
                'is_in_stock': variant.is_in_stock,
                'image': variant.image.url if variant.image else None,
                'attributes': variant.get_attribute_display(),
                'weight': float(variant.weight) if variant.weight else None
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
