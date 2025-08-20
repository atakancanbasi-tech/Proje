from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Order, OrderStatusHistory
from .email_utils import send_order_status_email, send_shipping_notification_email
from .utils.audit import get_current_user


@receiver(pre_save, sender=Order)
def _capture_old_status(sender, instance, **kwargs):
    """
    Güncelleme öncesi eski durumu yakala.
    """
    if not instance.pk:
        instance.__old_status = None
        return
    
    try:
        old = Order.objects.only('status').get(pk=instance.pk)
        instance.__old_status = getattr(old, 'status', None)
    except Order.DoesNotExist:
        instance.__old_status = None



@receiver(post_save, sender=Order)
def _log_status_transition(sender, instance, created, **kwargs):
    """
    Oluşturmada: None → status
    Güncellemede: eski → yeni (değişmişse)
    """
    old_status = getattr(instance, '__old_status', None)
    new_status = getattr(instance, 'status', None)
    
    if created:
        OrderStatusHistory.objects.create(
            order=instance,
            from_status=None,
            to_status=new_status,
            # callback/otomasyon için boş bırakıyoruz; middleware varsa kullanıcı otomatik dolacak
            changed_by=get_current_user(),
            note=''
        )
        return
    
    # Değişmemişse kayıt üretme
    if old_status == new_status:
        return
    
    OrderStatusHistory.objects.create(
        order=instance,
        from_status=old_status,
        to_status=new_status,
        changed_by=get_current_user(),
        note=''
    )


@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    """
    Sipariş kaydedildikten sonra e-posta bildirimleri gönderir
    """
    if created:
        # Yeni sipariş oluşturuldu
        send_order_status_email(instance)
    else:
        # Mevcut sipariş güncellendi
        status_changed = hasattr(instance, '__old_status') and instance.__old_status != instance.status
        
        # Sipariş durumu değiştiyse e-posta gönder
        if status_changed:
            send_order_status_email(instance, status_changed=True)