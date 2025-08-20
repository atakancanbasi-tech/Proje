from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_order_confirmation_email(order):
    """Sipariş onay e-postası gönder"""
    try:
        subject = f'Sipariş Onayı - #{order.number}'
        
        # HTML e-posta içeriği
        html_message = render_to_string('shop/emails/order_confirmation.html', {
            'order': order,
            'items': order.items.all()
        })
        
        # Düz metin versiyonu
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.email],
            html_message=html_message,
            fail_silently=False
        )
        
        return True
        
    except Exception as e:
        print(f'E-posta gönderme hatası: {e}')
        return False


def send_order_status_email(order, status_changed: bool = False):
    """Sipariş durum değişikliği e-postası gönder
    status_changed parametresi sinyal çağrısından gelir; şu anda sadece imza uyumluluğu için kullanılır.
    """
    try:
        # Durum mesajları
        status_messages = {
            'received': 'Siparişiniz alındı',
            'paid': 'Ödemeniz onaylandı',
            'shipped': 'Siparişiniz kargoya verildi',
            'cancelled': 'Siparişiniz iptal edildi'
        }
        
        status_message = status_messages.get(order.status, 'Sipariş durumu güncellendi')
        subject = f'{status_message} - #{order.number}'
        
        # HTML e-posta içeriği
        html_message = render_to_string('shop/emails/order_status.html', {
            'order': order,
            'status_message': status_message
        })
        
        # Düz metin versiyonu
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.email],
            html_message=html_message,
            fail_silently=False
        )
        
        return True
        
    except Exception as e:
        print(f'E-posta gönderme hatası: {e}')
        return False


def send_shipping_notification_email(order):
    """Kargo bildirim e-postası gönder"""
    try:
        subject = f'Siparişiniz Kargoya Verildi - #{order.number}'
        
        # HTML e-posta içeriği
        html_message = render_to_string('shop/emails/shipping_notification.html', {
            'order': order
        })
        
        # Düz metin versiyonu
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.email],
            html_message=html_message,
            fail_silently=False
        )
        
        return True
        
    except Exception as e:
        print(f'E-posta gönderme hatası: {e}')
        return False