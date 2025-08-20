from django.conf import settings


def calc_shipping(subtotal: float, method: str) -> float:
    """
    Kargo ücretini hesaplar.
    
    Args:
        subtotal: Sepet ara toplamı
        method: Kargo yöntemi ('standard' veya 'express')
    
    Returns:
        Kargo ücreti (float)
    """
    if subtotal >= settings.FREE_SHIPPING_THRESHOLD:
        return 0.0
    
    if method == "express":
        return settings.SHIPPING_EXPRESS
    else:
        return settings.SHIPPING_STANDARD


def get_shipping_methods():
    """
    Mevcut kargo yöntemlerini döndürür.
    
    Returns:
        List of tuples: (method_code, method_name, price)
    """
    return [
        ('standard', 'Standart Kargo', settings.SHIPPING_STANDARD),
        ('express', 'Hızlı Kargo', settings.SHIPPING_EXPRESS),
    ]