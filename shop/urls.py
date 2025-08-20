from django.urls import path
from django.shortcuts import redirect
from . import views
from .views.cart import checkout_fail, calculate_totals_ajax
from .views import order as order_views

app_name = 'shop'

# Redirect views for old URLs
def redirect_to_products(request):
    return redirect('shop:product_list', permanent=True)

def redirect_to_product_detail(request, pk):
    return redirect('shop:product_detail', pk=pk, permanent=True)

urlpatterns = [
    # Kanonik URL'ler
    path('products/', views.product_list, name='product_list'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    
    # Ana sayfa redirect (geçici - daha sonra home şablonu eklenecek)
    path('', redirect_to_products),
    
    # Eski alias'lar için 301 redirect'ler
    path('products/<int:pk>/', redirect_to_product_detail),

    # Sepet
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),

    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/pay/', views.checkout_pay, name='checkout_pay'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),
    path('checkout/fail/', checkout_fail, name='checkout_fail'),
    path('ajax/calculate-totals/', calculate_totals_ajax, name='calculate_totals_ajax'),
    
    # Kargo takip
    path('track-order/', views.track_order, name='track_order'),
    
    # Siparişler
    path('my-orders/', views.my_orders, name='my_orders'),
    path('order/<int:pk>/receipt/', order_views.order_receipt, name='order_receipt'),
    # Ürün arama
    path('search/autocomplete/', views.search_autocomplete, name='search_autocomplete'),
    path('search/advanced/', views.advanced_search, name='advanced_search'),
    
    # Ürün Varyantları
    path('product/<int:product_id>/variants/', views.get_product_variants, name='get_product_variants'),

    # Wishlist
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
]
