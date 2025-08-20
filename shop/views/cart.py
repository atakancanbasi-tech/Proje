from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import F
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import json
import time
import logging

logger = logging.getLogger(__name__)

from ..models import Product, Order, OrderItem
from ..cart import Cart
from ..forms import OrderForm, BillingForm
from ..utils import calculate_order_totals
from ..shipping import calc_shipping, get_shipping_methods
from accounts.models import Address
from payments.provider import get_provider


def cart_detail(request):
    cart = Cart(request)
    return render(request, 'shop/cart_detail.html', {'cart': cart})


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
    except (ValueError, TypeError):
        messages.error(request, 'Geçersiz miktar')
        return redirect('shop:product_detail', pk=product_id)
    
    # Stok kontrolü
    if hasattr(product, 'stock') and product.stock < quantity:
        messages.error(request, 'Yetersiz stok')
        return redirect('shop:product_detail', pk=product_id)
    
    cart.add(product=product, quantity=quantity)
    messages.success(request, f'{product.name} sepete eklendi')
    return redirect('shop:cart_detail')


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    messages.success(request, f'{product.name} sepetten çıkarıldı')
    return redirect('shop:cart_detail')


@require_POST
def cart_update(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity <= 0:
            cart.remove(product)
            messages.success(request, f'{product.name} sepetten çıkarıldı')
        else:
            # Stok kontrolü
            if hasattr(product, 'stock') and product.stock < quantity:
                messages.error(request, 'Yetersiz stok')
                return redirect('shop:cart_detail')
            
            cart.add(product=product, quantity=quantity, override_quantity=True)
            messages.success(request, 'Sepet güncellendi')
    except (ValueError, TypeError):
        messages.error(request, 'Geçersiz miktar')
    
    return redirect('shop:cart_detail')


def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, 'Sepetiniz boş')
        return redirect('shop:cart_detail')
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        billing_form = BillingForm(request.POST)
        if form.is_valid() and billing_form.is_valid():
            # Form verilerini session'a kaydet
            checkout_data = form.cleaned_data.copy()
            
            # Kargo bilgilerini ekle
            checkout_data['shipping_method'] = request.POST.get('shipping', 'standard')
            
            # Fatura bilgilerini snapshot olarak ekle
            checkout_data['billing'] = billing_form.cleaned_data
            
            # Seçilen adres bilgilerini ekle
            if request.user.is_authenticated:
                selected_address_id = request.POST.get('selected_address')
                save_new_address = request.POST.get('save_address') == 'on'
                
                if selected_address_id and selected_address_id != 'new':
                    try:
                        address = Address.objects.get(id=selected_address_id, user=request.user)
                        checkout_data.update({
                            'selected_address_id': address.id,
                            'fullname': address.fullname,
                            'phone': address.phone,
                            'address': address.address,
                            'city': address.city,
                            'district': address.district,
                            'postal_code': address.postal_code,
                        })
                    except Address.DoesNotExist:
                        pass
                elif save_new_address:
                    checkout_data['save_new_address'] = True
            
            request.session['checkout_data'] = checkout_data
            return redirect('shop:checkout_pay')
    else:
        # Kullanıcı bilgileri varsa form'u doldur
        initial_data = {}
        if request.user.is_authenticated:
            initial_data.update({
                'email': request.user.email,
                'fullname': f"{request.user.first_name} {request.user.last_name}".strip(),
            })
        form = OrderForm(initial=initial_data)
        billing_form = BillingForm()
    
    cart_items = []
    for item in cart:
        cart_items.append({
            'product': item['product'],
            'quantity': item['quantity'],
            'price': item['price'],
            'total_price': item['total_price']
        })
    
    # Toplam hesaplama
    totals = calculate_order_totals(cart_items)
    
    # Kullanıcının adresleri
    user_addresses = []
    if request.user.is_authenticated:
        user_addresses = Address.objects.filter(user=request.user)
    
    # Kargo seçenekleri
    shipping_methods = get_shipping_methods()
    
    context = {
        'form': form,
        'billing_form': billing_form,
        'cart': cart,
        'cart_items': cart_items,
        'totals': totals,
        'user_addresses': user_addresses,
        'shipping_methods': shipping_methods,
        'free_shipping_threshold': settings.FREE_SHIPPING_THRESHOLD
    }
    
    return render(request, 'shop/checkout.html', context)


def checkout_pay(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, 'Sepetiniz boş')
        return redirect('shop:cart_detail')
    
    checkout_data = request.session.get('checkout_data')
    if not checkout_data:
        messages.error(request, 'Checkout bilgileri bulunamadı')
        return redirect('shop:checkout')
    
    if request.method == 'POST':
        try:
            provider = get_provider(settings)
            cart_items = []
            for item in cart:
                cart_items.append({
                    'product': item['product'],
                    'quantity': item['quantity'],
                    'price': item['price'],
                    'total_price': item['total_price']
                })
            
            shipping_method = checkout_data.get('shipping_method', 'standard')
            subtotal = sum(item['total_price'] for item in cart_items)
            shipping_fee = calc_shipping(float(subtotal), shipping_method)
            total_amount = float(subtotal) + shipping_fee
            
            totals = {
                'subtotal': subtotal,
                'shipping_fee': shipping_fee,
                'total': total_amount
            }
            
            provider_name = getattr(settings, 'PAYMENT_PROVIDER', 'mock').lower()
            
            billing = checkout_data.get('billing') or {}
            want_invoice = billing.get('want_invoice')
            invoice_update_fields = []
            
            if provider_name == 'mock':
                payment_result = provider.charge(
                    amount=total_amount,
                    currency='TRY',
                    order_ref=f'ORDER-{int(time.time())}'
                )
                if payment_result.success:
                    with transaction.atomic():
                        if (request.user.is_authenticated and 
                            checkout_data.get('save_new_address') and 
                            not checkout_data.get('selected_address_id')):
                            Address.objects.create(
                                user=request.user,
                                title='Yeni Adres',
                                fullname=checkout_data.get('fullname', ''),
                                phone=checkout_data.get('phone', ''),
                                address=checkout_data.get('address', ''),
                                city=checkout_data.get('city', ''),
                                district=checkout_data.get('district', ''),
                                postal_code=checkout_data.get('postal_code', ''),
                                is_default=False
                            )
                        order = Order.objects.create(
                            user=request.user if request.user.is_authenticated else None,
                            email=checkout_data.get('email', request.user.email if request.user.is_authenticated else 'test@example.com'),
                            fullname=checkout_data.get('fullname', 'Test Kullanıcı'),
                            phone=checkout_data.get('phone', ''),
                            address=checkout_data.get('address', ''),
                            city=checkout_data.get('city', ''),
                            district=checkout_data.get('district', ''),
                            postal_code=checkout_data.get('postal_code', ''),
                            shipping_method=shipping_method,
                            shipping_fee=shipping_fee,
                            total=total_amount,
                            status='paid',
                        )
                        # Fatura snapshot
                        if want_invoice:
                            order.invoice_type = billing.get('invoice_type') or 'bireysel'
                            order.billing_fullname = billing.get('billing_fullname','') or order.fullname
                            order.tckn = billing.get('tckn','')
                            order.vkn = billing.get('vkn','')
                            order.tax_office = billing.get('tax_office','')
                            order.e_archive_email = billing.get('e_archive_email','')
                            order.billing_address = billing.get('billing_address','')
                            order.billing_city = billing.get('billing_city','')
                            order.billing_district = billing.get('billing_district','')
                            order.billing_postcode = billing.get('billing_postcode','')
                            order.kvkk_approved = bool(billing.get('kvkk_approved'))
                            invoice_update_fields = ['invoice_type','billing_fullname','tckn','vkn','tax_office','e_archive_email','billing_address','billing_city','billing_district','billing_postcode','kvkk_approved']
                            order.save(update_fields=invoice_update_fields + ['status'])
                        
                        for item in cart:
                            product = item['product']
                            quantity = item['quantity']
                            unit_price = item['price']
                            line_total = item['total_price']
                            OrderItem.objects.create(
                                order=order,
                                product=product,
                                quantity=quantity,
                                unit_price=unit_price,
                                line_total=line_total
                            )
                            if hasattr(product, 'stock'):
                                Product.objects.filter(id=product.id).update(stock=F('stock') - quantity)
                                product.refresh_from_db()
                                if product.stock < 0:
                                    transaction.set_rollback(True)
                                    messages.error(request, f'{product.name} için stok yetersiz')
                                    return redirect('shop:checkout')
                        cart.clear()
                        request.session['last_order_id'] = order.id
                        if 'checkout_data' in request.session:
                            del request.session['checkout_data']
                        return redirect('shop:checkout_success')
                else:
                    messages.error(request, 'Ödeme işlemi başarısız oldu')
                    return redirect('shop:checkout')
            else:
                with transaction.atomic():
                    order = Order.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        email=checkout_data.get('email', request.user.email if request.user.is_authenticated else 'test@example.com'),
                        fullname=checkout_data.get('fullname', 'Test Kullanıcı'),
                        phone=checkout_data.get('phone', ''),
                        address=checkout_data.get('address', ''),
                        city=checkout_data.get('city', ''),
                        district=checkout_data.get('district', ''),
                        postal_code=checkout_data.get('postal_code', ''),
                        shipping_method=shipping_method,
                        shipping_fee=shipping_fee,
                        total=total_amount,
                        status='received',
                    )
                    # Fatura snapshot
                    if want_invoice:
                        order.invoice_type = billing.get('invoice_type') or 'bireysel'
                        order.billing_fullname = billing.get('billing_fullname','') or order.fullname
                        order.tckn = billing.get('tckn','')
                        order.vkn = billing.get('vkn','')
                        order.tax_office = billing.get('tax_office','')
                        order.e_archive_email = billing.get('e_archive_email','')
                        order.billing_address = billing.get('billing_address','')
                        order.billing_city = billing.get('billing_city','')
                        order.billing_district = billing.get('billing_district','')
                        order.billing_postcode = billing.get('billing_postcode','')
                        order.kvkk_approved = bool(billing.get('kvkk_approved'))
                        order.save(update_fields=['invoice_type','billing_fullname','tckn','vkn','tax_office','e_archive_email','billing_address','billing_city','billing_district','billing_postcode','kvkk_approved'])
                    
                    for item in cart:
                        product = item['product']
                        quantity = item['quantity']
                        unit_price = item['price']
                        line_total = item['total_price']
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=quantity,
                            unit_price=unit_price,
                            line_total=line_total
                        )
                    payment_result = provider.initiate(
                        order=order,
                        amount=total_amount,
                        currency='TRY',
                        request=request
                    )
                    if payment_result.success and payment_result.requires_redirect:
                        cart.clear()
                        if 'checkout_data' in request.session:
                            del request.session['checkout_data']
                        from django.http import HttpResponse
                        return HttpResponse(payment_result.form_html)
                    else:
                        messages.error(request, payment_result.message or 'Ödeme sağlayıcı hatası')
                        return redirect('shop:checkout')
        except Exception as e:
            messages.error(request, f'Bir hata oluştu: {str(e)}')
            return redirect('shop:checkout')
    
    cart_items = []
    for item in cart:
        cart_items.append({
            'product': item['product'],
            'quantity': item['quantity'],
            'price': item['price'],
            'total_price': item['total_price']
        })
    totals = calculate_order_totals(cart_items)
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'totals': totals,
        'checkout_data': checkout_data
    }
    return render(request, 'shop/checkout_pay.html', context)


def checkout_success(request):
    last_order_id = request.session.get('last_order_id')
    last_order_number = None
    
    if last_order_id:
        try:
            order = Order.objects.get(id=last_order_id)
            last_order_number = order.number
            # Session'dan sil
            del request.session['last_order_id']
        except Order.DoesNotExist:
            pass
    
    context = {
        'last_order_number': last_order_number
    }
    
    return render(request, 'shop/checkout_success.html', context)


def checkout_fail(request):
    """Ödeme başarısız sayfası"""
    return render(request, 'shop/checkout_fail.html')


@csrf_exempt
@require_POST
def calculate_totals_ajax(request):
    """AJAX ile toplam hesaplama"""
    try:
        data = json.loads(request.body)
        cart = Cart(request)
        shipping_method = data.get('shipping_method', 'standard')
        
        cart_items = []
        for item in cart:
            cart_items.append({
                'product': item['product'],
                'quantity': item['quantity'],
                'price': item['price'],
                'total_price': item['total_price']
            })
        
        # Kargo hesaplama
        subtotal = sum(item['total_price'] for item in cart_items)
        shipping_fee = calc_shipping(float(subtotal), shipping_method)
        total = float(subtotal) + shipping_fee
        
        return JsonResponse({
            'success': True,
            'totals': {
                'subtotal': float(subtotal),
                'shipping_fee': float(shipping_fee),
                'total': float(total)
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })