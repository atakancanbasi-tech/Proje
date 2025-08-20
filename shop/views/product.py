from django.shortcuts import render, get_object_or_404, redirect
from ..models import Product, Category, OrderItem, Review, Wishlist, StockAlert, ProductAttribute, ProductAttributeValue, ProductVariant, ProductVariantAttribute
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count, Min, Max
from django.http import JsonResponse
from django.db import models
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json

# Ürün listesi

def product_list(request):
    # Ana sayfa kontrolü
    is_homepage = not any(request.GET.get(param) for param in ['q', 'category', 'min_price', 'max_price', 'sort'])
    
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
    
    # Filtreleme sayfası için mevcut kod
    products = Product.objects.select_related('category').only(
        'id', 'name', 'price', 'stock', 'image', 'category__name', 'created_at'
    )
    
    # Arama
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    
    # Kategori filtresi
    category_id = request.GET.get('category', '').strip()
    if category_id and category_id.isdigit():
        products = products.filter(category_id=int(category_id))
    
    # Fiyat aralığı filtresi - validasyon ve normalizasyon
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    
    # Min price validasyonu
    if min_price:
        try:
            min_price_val = float(min_price)
            if min_price_val < 0:
                min_price_val = 0
            products = products.filter(price__gte=min_price_val)
            min_price = str(min_price_val)
        except (ValueError, TypeError):
            min_price = ''
    
    # Max price validasyonu
    if max_price:
        try:
            max_price_val = float(max_price)
            if max_price_val < 0:
                max_price_val = 0
            products = products.filter(price__lte=max_price_val)
            max_price = str(max_price_val)
        except (ValueError, TypeError):
            max_price = ''
    
    # Ters aralık normalizasyonu
    if min_price and max_price:
        try:
            min_val = float(min_price)
            max_val = float(max_price)
            if min_val > max_val:
                min_price, max_price = max_price, min_price
        except (ValueError, TypeError):
            pass
    
    # Sıralama - new varsayılan
    sort_by = request.GET.get('sort', 'new')
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'new':
        # created_at varsa onu kullan, yoksa -id
        if hasattr(Product, 'created_at'):
            products = products.order_by('-created_at')
        else:
            products = products.order_by('-id')
    else:  # new (default)
        if hasattr(Product, 'created_at'):
            products = products.order_by('-created_at')
        else:
            products = products.order_by('-id')
    
    categories = Category.objects.all()
    
    # Fiyat aralığı için min/max değerleri
    price_range = Product.objects.aggregate(
        min_price=models.Min('price'),
        max_price=models.Max('price')
    )
    
    # Sayfalama
    paginator = Paginator(products, 12)  # 12 ürün per sayfa
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # SEO için canonical URL ve noindex kontrolü
    has_filters = bool(q or category_id or min_price or max_price or sort_by != 'new')
    canonical_url = request.build_absolute_uri(request.path)
    
    context = {
        'is_homepage': False,
        'page_obj': page_obj,
        'products': page_obj,  # Template uyumluluğu için
        'categories': categories,
        'q': q,
        'selected_category': int(category_id) if category_id and category_id.isdigit() else '',
        'min_price': min_price,
        'max_price': max_price,
        'sort_by': sort_by,
        'price_range': price_range,
        'has_filters': has_filters,
        'canonical_url': canonical_url,
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
    
    # İlgili ürünler (aynı kategori, 4 adet)
    related = Product.objects.filter(category=product.category)\
               .exclude(pk=pk).select_related('category')[:4]
    
    context = {
        'product': product,
        'reviews': reviews,
        'user_review': user_review,
        'can_review': can_review,
        'has_purchased': has_purchased,
        'is_in_wishlist': is_in_wishlist,
        'has_active_stock_alert': has_active_stock_alert,
        'related_products': related,
    }
    return render(request, 'shop/product_detail.html', context)

@require_http_methods(["GET"])
def get_product_variants(request, product_id):
    """Ürün varyantlarını JSON olarak döndür"""
    try:
        product = get_object_or_404(Product, id=product_id)
        variants = product.variants.prefetch_related('attributes__attribute').all()
        
        # Varyant verilerini hazırla
        variant_data = []
        for variant in variants:
            attributes = {}
            for attr in variant.attributes.all():
                attributes[attr.attribute.name] = {
                    'value': attr.value,
                    'display_value': attr.display_value or attr.value,
                    'color_code': attr.color_code
                }
            
            variant_data.append({
                'id': variant.id,
                'sku': variant.sku,
                'price': float(variant.price),
                'stock': variant.stock,
                'attributes': attributes,
                'is_available': variant.stock > 0
            })
        
        # Mevcut öznitelikleri grupla
        attributes = {}
        for variant in variants:
            for attr in variant.attributes.all():
                attr_name = attr.attribute.name
                if attr_name not in attributes:
                    attributes[attr_name] = {
                        'display_name': attr.attribute.display_name or attr_name,
                        'values': []
                    }
                
                value_data = {
                    'id': attr.id,
                    'value': attr.value,
                    'display_value': attr.display_value or attr.value,
                    'color_code': attr.color_code
                }
                
                # Aynı değeri tekrar ekleme
                if not any(v['value'] == value_data['value'] for v in attributes[attr_name]['values']):
                    attributes[attr_name]['values'].append(value_data)
        
        return JsonResponse({
            'success': True,
            'variants': variant_data,
            'attributes': attributes
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_http_methods(["GET"])
def search_autocomplete(request):
    """Arama önerileri için AJAX endpoint"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    # Ürün önerileri
    products = Product.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query)
    ).only('id', 'name', 'price', 'image').order_by('name')[:8]
    
    # Kategori önerileri
    categories = Category.objects.filter(
        name__icontains=query
    ).only('id', 'name')[:5]
    
    suggestions = []
    
    # Ürün önerilerini ekle
    for product in products:
        suggestions.append({
            'type': 'product',
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'image': product.image.url if product.image else None,
            'url': f'/shop/product/{product.id}/'
        })
    
    # Kategori önerilerini ekle
    for category in categories:
        suggestions.append({
            'type': 'category',
            'id': category.id,
            'name': category.name,
            'url': f'/shop/products/?category={category.id}'
        })
    
    return JsonResponse({'suggestions': suggestions})

@require_http_methods(["GET"])
def advanced_search(request):
    """Gelişmiş arama sayfası"""
    products = Product.objects.select_related('category').all()
    categories = Category.objects.all()
    
    # Arama parametreleri
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    in_stock = request.GET.get('in_stock')
    min_rating = request.GET.get('min_rating', '').strip()
    sort_by = request.GET.get('sort', 'name')
    
    # Filtreleme
    if q:
        products = products.filter(
            Q(name__icontains=q) | 
            Q(description__icontains=q) |
            Q(category__name__icontains=q)
        )
    
    if category_id.isdigit():
        products = products.filter(category_id=int(category_id))
    
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
    
    if in_stock == 'true':
        products = products.filter(stock__gt=0)
    elif in_stock == 'false':
        products = products.filter(stock=0)
    
    if min_rating:
        try:
            rating = int(min_rating)
            if 1 <= rating <= 5:
                products = products.annotate(
                    avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
                ).filter(avg_rating__gte=rating)
        except ValueError:
            pass
    
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
    elif sort_by == 'oldest':
        products = products.order_by('id')
    else:  # name (default)
        products = products.order_by('name')
    
    # Sayfalama
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Fiyat aralığı
    price_range = Product.objects.aggregate(
        min_price=models.Min('price'),
        max_price=models.Max('price')
    )
    
    context = {
        'products': page_obj,
        'categories': categories,
        'query': q,
        'selected_category': int(category_id) if category_id.isdigit() else '',
        'min_price': min_price,
        'max_price': max_price,
        'in_stock': in_stock,
        'min_rating': min_rating,
        'sort_by': sort_by,
        'price_range': price_range,
        'page_obj': page_obj,
    }
    return render(request, 'shop/advanced_search.html', context)