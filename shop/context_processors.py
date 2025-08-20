from .cart import Cart

def cart_info(request):
    cart = Cart(request)
    try:
        total = cart.get_total_price()
    except Exception:
        total = 0
    return {
        'cart_item_count': len(cart),
        'cart_total_price': total,
    }