from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter(name='money')
def money(value):
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