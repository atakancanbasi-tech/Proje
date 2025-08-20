# View modüllerinden tüm view'ları dışa aktar

# Product views
from .product import (
    product_list,
    product_detail,
    get_product_variants,
    search_autocomplete,
    advanced_search
)

# Cart views
from .cart import (
    cart_add,
    cart_remove,
    cart_update,
    cart_detail,
    checkout,
    checkout_success,
    checkout_pay
)

# Order views
from .order import (
    my_orders,
    order_detail,
    track_order,
    add_review,
    edit_review,
    delete_review
)

# Account views
from .account import (
    wishlist_view,
    add_to_wishlist,
    remove_from_wishlist,
    create_stock_alert,
    cancel_stock_alert,
    my_stock_alerts,
    check_stock_alerts
)

# Ana sayfa için alias
home = product_list

# Tüm view'ları listele (isteğe bağlı)
__all__ = [
    # Product views
    'product_list',
    'product_detail',
    'get_product_variants',
    'search_autocomplete',
    'advanced_search',
    'home',
    
    # Cart views
    'cart_add',
    'decrement_from_cart',
    'update_cart_quantity',
    'view_cart',
    'remove_from_cart',
    'checkout',
    'checkout_success',
    'checkout_pay',
    'checkout_fail',
    'calculate_checkout_totals',
    'validate_coupon',
    'remove_coupon',
    'get_user_coupons',
    'add_variant_to_cart',
    'get_variant_details',
    
    # Order views
    'my_orders',
    'order_detail',
    'track_order',
    'add_review',
    'edit_review',
    'delete_review',
    
    # Account views
    'wishlist_view',
    'add_to_wishlist',
    'remove_from_wishlist',
    'create_stock_alert',
    'cancel_stock_alert',
    'my_stock_alerts',
    'check_stock_alerts',
]