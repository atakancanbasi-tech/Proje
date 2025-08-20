class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        self.cart = cart

    def add(self, product, quantity=1, variant_id=None):
        # Varyant varsa ürün_id:varyant_id formatında key oluştur
        if variant_id:
            cart_key = f"{product.id}:{variant_id}"
            from .models import ProductVariant
            variant = ProductVariant.objects.get(id=variant_id)
            price = variant.effective_price
        else:
            cart_key = str(product.id)
            price = product.price
            
        if cart_key not in self.cart:
            self.cart[cart_key] = {
                'quantity': 0, 
                'price': str(price),
                'variant_id': variant_id
            }
        self.cart[cart_key]['quantity'] += quantity
        self.save()

    def decrement(self, product, quantity=1, variant_id=None):
        cart_key = f"{product.id}:{variant_id}" if variant_id else str(product.id)
        if cart_key in self.cart:
            self.cart[cart_key]['quantity'] -= quantity
            if self.cart[cart_key]['quantity'] <= 0:
                del self.cart[cart_key]
            self.save()

    def remove(self, product, variant_id=None):
        cart_key = f"{product.id}:{variant_id}" if variant_id else str(product.id)
        if cart_key in self.cart:
            del self.cart[cart_key]
            self.save()

    def set(self, product, quantity, variant_id=None):
        """Ürünün sepet miktarını kesin olarak ayarla. 0 veya altı ise ürünü kaldır."""
        cart_key = f"{product.id}:{variant_id}" if variant_id else str(product.id)
        
        if quantity <= 0:
            if cart_key in self.cart:
                del self.cart[cart_key]
        else:
            # Fiyat hesapla
            if variant_id:
                from .models import ProductVariant
                variant = ProductVariant.objects.get(id=variant_id)
                price = variant.effective_price
            else:
                price = product.price
                
            # yoksa ekle, varsa güncelle
            if cart_key not in self.cart:
                self.cart[cart_key] = {
                    'quantity': 0, 
                    'price': str(price),
                    'variant_id': variant_id
                }
            self.cart[cart_key]['quantity'] = int(quantity)
            # Fiyat güncelleme (ürün fiyatı değişmiş olabilir)
            self.cart[cart_key]['price'] = str(price)
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        from .models import Product, ProductVariant
        for cart_key, item in self.cart.items():
            # Cart key formatını kontrol et (product_id veya product_id:variant_id)
            # Session'a kaydedilmemesi için yeni bir dict oluştur
            cart_item = item.copy()
            
            if ':' in cart_key:
                product_id, variant_id = cart_key.split(':')
                product = Product.objects.get(id=product_id)
                variant = ProductVariant.objects.get(id=variant_id)
                cart_item['product'] = product
                cart_item['variant'] = variant
                cart_item['total_price'] = variant.effective_price * cart_item['quantity']
            else:
                product = Product.objects.get(id=cart_key)
                cart_item['product'] = product
                cart_item['variant'] = None
                cart_item['total_price'] = product.price * cart_item['quantity']
            yield cart_item

    def clear(self):
        self.session['cart'] = {}
        self.save()

    def __len__(self):
        # Sepetteki toplam ürün adedi
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        # Sepetteki kalemlerin toplam tutarı
        from decimal import Decimal
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())

    # Yardımcı: bir ürünün sepetteki mevcut miktarı
    def get_quantity(self, product, variant_id=None):
        cart_key = f"{product.id}:{variant_id}" if variant_id else str(product.id)
        return self.cart.get(cart_key, {}).get('quantity', 0)
