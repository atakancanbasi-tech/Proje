from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from decimal import Decimal
from ..models import ShippingCompany, PaymentMethod
from ..models import Order, OrderItem
import logging

logger = logging.getLogger(__name__)


def send_order_confirmation_email(order):
    """
    Sipariş onayı e-postası gönderir
    """
    try:
        # Sipariş ürünlerini al
        order_items = OrderItem.objects.filter(order=order).select_related('product')
        
        # E-posta şablonunu render et
        html_message = render_to_string('emails/order_confirmation.html', {
            'order': order,
            'order_items': order_items,
        })
        
        # HTML'den düz metin oluştur
        plain_message = strip_tags(html_message)
        
        # E-posta gönder
        subject = f'Sipariş Onayı - #{order.id}'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [order.email]
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f'Sipariş onayı e-postası gönderildi: {order.email} - Sipariş #{order.id}')
        return True
        
    except Exception as e:
        logger.error(f'Sipariş onayı e-postası gönderilemedi: {order.email} - Sipariş #{order.id} - Hata: {str(e)}')
        return False


def send_order_status_update_email(order, old_status, new_status):
    """
    Sipariş durumu değişiklik e-postası gönderir
    """
    try:
        # Sipariş ürünlerini al
        order_items = OrderItem.objects.filter(order=order).select_related('product')
        
        # Durum açıklamalarını hazırla
        status_messages = {
            'received': 'Siparişiniz alınmıştır ve işleme alınmayı beklemektedir.',
            'paid': 'Siparişiniz işleme alınmıştır ve hazırlanmaktadır.',
            'shipped': 'Siparişiniz kargoya verilmiştir ve yola çıkmıştır.',
            'cancelled': 'Siparişiniz iptal edilmiştir.'
        }
        
        status_display = {
            'received': 'Alındı',
            'paid': 'Ödendi',
            'shipped': 'Kargolandı',
            'cancelled': 'İptal'
        }
        
        # E-posta şablonunu render et
        html_message = render_to_string('emails/order_status_update.html', {
            'order': order,
            'order_items': order_items,
            'old_status': old_status,
            'new_status': new_status,
            'old_status_display': status_display.get(old_status, old_status),
            'new_status_display': status_display.get(new_status, new_status),
            'status_message': status_messages.get(new_status, 'Sipariş durumunuz güncellenmiştir.')
        })
        
        # HTML'den düz metin oluştur
        plain_message = strip_tags(html_message)
        
        # E-posta gönder
        subject = f'Sipariş Durumu Güncellendi - #{order.id}'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [order.email]
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f'Sipariş durumu güncelleme e-postası gönderildi: {order.email} - Sipariş #{order.id} - {old_status} -> {new_status}')
        return True
        
    except Exception as e:
        logger.error(f'Sipariş durumu güncelleme e-postası gönderilemedi: {order.email} - Sipariş #{order.id} - Hata: {str(e)}')
        return False


def get_order_status_display(status):
    """Sipariş durumu için Türkçe açıklama döndür"""
    status_dict = {
        'received': 'Alındı',
        'paid': 'Ödendi',
        'shipped': 'Kargolandı',
        'cancelled': 'İptal',
    }
    return status_dict.get(status, status)



def calculate_shipping_options(cart_total, cart_weight=None):
    """Mevcut kargo seçeneklerini ve ücretlerini hesapla"""
    if cart_weight is None:
        cart_weight = 1  # Varsayılan ağırlık
    
    shipping_options = []
    active_companies = ShippingCompany.objects.filter(is_active=True)
    
    for company in active_companies:
        cost = company.calculate_shipping_cost(cart_total, cart_weight)
        shipping_options.append({
            'id': company.id,
            'name': company.name,
            'cost': cost,
            'estimated_days': company.estimated_delivery_days,
            'is_free': cost == 0,
            'free_threshold': company.free_shipping_threshold
        })
    
    # Ücrete göre sırala
    shipping_options.sort(key=lambda x: x['cost'])
    return shipping_options


def get_available_payment_methods(order_amount=None):
    """Mevcut ödeme yöntemlerini getir"""
    from django.db.models import Q
    
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    
    if order_amount:
        # Tutar sınırlarına göre filtrele
        payment_methods = payment_methods.filter(
            Q(min_amount__isnull=True) | Q(min_amount__lte=order_amount),
            Q(max_amount__isnull=True) | Q(max_amount__gte=order_amount)
        )
    
    return payment_methods


def calculate_order_totals(cart_items, shipping_company_id=None, payment_method_id=None):
    """Sipariş toplamlarını hesapla"""
    from django.db import models
    
    # Alt toplam hesapla
    subtotal = sum(Decimal(str(item['price'])) * item['quantity'] for item in cart_items)
    
    # Kargo ücreti hesapla
    shipping_cost = Decimal('0.00')
    if shipping_company_id:
        try:
            shipping_company = ShippingCompany.objects.get(id=shipping_company_id, is_active=True)
            total_weight = sum(item['quantity'] for item in cart_items)  # Basit ağırlık hesabı
            shipping_cost = shipping_company.calculate_shipping_cost(subtotal, total_weight)
        except ShippingCompany.DoesNotExist:
            pass
    
    # İşlem ücreti hesapla
    processing_fee = Decimal('0.00')
    if payment_method_id:
        try:
            payment_method = PaymentMethod.objects.get(id=payment_method_id, is_active=True)
            processing_fee = payment_method.calculate_processing_fee(subtotal)
        except PaymentMethod.DoesNotExist:
            pass
    
    # Toplam hesapla
    total_amount = subtotal + shipping_cost + processing_fee
    
    return {
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'processing_fee': processing_fee,
        'total': total_amount
    }