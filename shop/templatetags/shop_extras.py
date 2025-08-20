from django import template
from decimal import Decimal, InvalidOperation
from django.template.loader import get_template
from django.template import TemplateDoesNotExist

register = template.Library()

@register.filter(name='currency')
def currency(value):
    """Decimal fiyatları 2 ondalık ve ₺ ile biçimlendirir.
    Örn: 1234.5 -> 1.234,50 ₺ (TR formatına yakın ama basit)
    """
    try:
        dec = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    # Basit TR format: binlik ayırıcı nokta, ondalık virgül
    s = f"{dec:,.2f}"  # 1,234.50
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")  # 1.234,50
    return f"{s} ₺"

@register.filter(name='money')
def money(value):
    """currency filter'ın alias'ı"""
    return currency(value)

@register.simple_tag
def order_status_badge(status):
    """Sipariş durumu için Bootstrap badge class'ı döndürür"""
    status_classes = {
        'pending': 'bg-warning',
        'processing': 'bg-info', 
        'shipped': 'bg-primary',
        'delivered': 'bg-success',
        'cancelled': 'bg-danger'
    }
    return status_classes.get(status, 'bg-secondary')

@register.simple_tag
def order_status_text(status):
    """Sipariş durumu için Türkçe metin döndürür"""
    status_texts = {
        'pending': 'Beklemede',
        'processing': 'İşleniyor',
        'shipped': 'Kargoda', 
        'delivered': 'Teslim Edildi',
        'cancelled': 'İptal Edildi'
    }
    return status_texts.get(status, 'Bilinmiyor')

@register.simple_tag(takes_context=True)
def safe_include(context, template_path):
    """
    Verilen template_path mevcutsa içeri alır, yoksa boş string döndürür.
    Kullanım: {% load shop_extras %} {% safe_include "shop/partials/_mega_menu.html" %}
    """
    try:
        tmpl = get_template(template_path)
    except TemplateDoesNotExist:
        return ""
    # include benzeri: mevcut context ile render
    return tmpl.render(context.flatten())