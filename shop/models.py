from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils import timezone

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.stock > 0
    
    @property
    def average_rating(self):
        """Ürünün ortalama puanını hesaplar"""
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return reviews.aggregate(models.Avg('rating'))['rating__avg']
        return 0
    
    @property
    def review_count(self):
        """Onaylanmış yorum sayısını döndürür"""
        return self.reviews.filter(is_approved=True).count()
    
    @property
    def rating_distribution(self):
        """Yıldız dağılımını hesaplar"""
        from django.db.models import Count
        reviews = self.reviews.filter(is_approved=True)
        distribution = {i: 0 for i in range(1, 6)}
        
        rating_counts = reviews.values('rating').annotate(count=Count('rating'))
        for item in rating_counts:
            distribution[item['rating']] = item['count']
        
        return distribution


class ShippingCompany(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    base_price = models.DecimalField(max_digits=8, decimal_places=2)
    price_per_kg = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    estimated_delivery_days = models.PositiveIntegerField(default=3)
    
    def __str__(self):
        return self.name
    
    def calculate_shipping_cost(self, total_amount, weight=1):
        """Kargo ücreti hesapla"""
        if self.free_shipping_threshold and total_amount >= self.free_shipping_threshold:
            return Decimal('0.00')
        return self.base_price + (self.price_per_kg * Decimal(str(weight)))
    
    class Meta:
        verbose_name_plural = "Shipping Companies"


class PaymentMethod(models.Model):
    PAYMENT_TYPES = [
        ('credit_card', 'Kredi Kartı'),
        ('bank_transfer', 'Banka Havalesi'),
        ('cash_on_delivery', 'Kapıda Ödeme'),
        ('digital_wallet', 'Dijital Cüzdan'),
    ]
    
    name = models.CharField(max_length=100)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    is_active = models.BooleanField(default=True)
    processing_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name
    
    def calculate_processing_fee(self, amount):
        """İşlem ücreti hesapla"""
        return amount * (self.processing_fee_percentage / 100)
    
    class Meta:
        verbose_name_plural = "Payment Methods"


class Order(models.Model):
    STATUS_CHOICES = [('received','Alındı'),('paid','Ödendi'),('shipped','Kargolandı'),('cancelled','İptal')]
    SHIPPING_CHOICES = [('standard', 'Standart Kargo'), ('express', 'Hızlı Kargo')]
    
    class InvoiceType(models.TextChoices):
        BIREYSEL = "bireysel", "Bireysel"
        KURUMSAL = "kurumsal", "Kurumsal"
    
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField()
    fullname = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    address = models.TextField()
    city = models.CharField(max_length=60)
    district = models.CharField(max_length=60, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_method = models.CharField(max_length=20, choices=SHIPPING_CHOICES, default='standard')
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='received')
    created_at = models.DateTimeField(auto_now_add=True)
    # Payment fields
    payment_provider = models.CharField(max_length=20, blank=True, default='')
    payment_ref = models.CharField(max_length=128, blank=True, null=True, unique=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    
    # --- Fatura (opsiyonel) ---
    INVOICE_TYPE_CHOICES = (
        ('bireysel', 'Bireysel'),
        ('kurumsal', 'Kurumsal'),
    )
    
    invoice_type = models.CharField('Fatura Tipi', max_length=10, choices=INVOICE_TYPE_CHOICES, default='bireysel')
    billing_fullname = models.CharField('Fatura Ad Soyad/Ünvan', max_length=255, blank=True)
    tax_office = models.CharField('Vergi Dairesi', max_length=128, blank=True)
    tckn = models.CharField(
        'TCKN', max_length=11, blank=True,
        validators=[RegexValidator(r'^\d{11}$', 'TCKN 11 haneli rakam olmalıdır.')],
    )
    vkn = models.CharField(
        'VKN', max_length=10, blank=True,
        validators=[RegexValidator(r'^\d{10}$', 'VKN 10 haneli rakam olmalıdır.')],
    )
    e_archive_email = models.EmailField('E-Arşiv E-posta', blank=True)
    billing_address = models.CharField('Fatura Adresi', max_length=500, blank=True)
    billing_city = models.CharField('İl', max_length=64, blank=True)
    billing_district = models.CharField('İlçe', max_length=64, blank=True)
    billing_postcode = models.CharField('Posta Kodu', max_length=10, blank=True)
    kvkk_approved = models.BooleanField('KVKK Aydınlatma Onayı', default=False)

    @property
    def number(self):
        return f"ORD{self.created_at:%Y%m%d}{self.id}"

    def __str__(self):
        return self.number


class OrderStatusHistory(models.Model):
    """
    Sipariş durum geçişleri için izleme kaydı.
    """
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=32, null=True, blank=True)
    to_status = models.CharField(max_length=32)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='order_status_changes'
    )
    note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Sipariş Durum Geçişi"
        verbose_name_plural = "Sipariş Durum Geçişleri"
        indexes = [
            models.Index(fields=['order', 'created_at']),
        ]
    
    def __str__(self):
        return f"#{self.order_id}: {self.from_status or '—'} → {self.to_status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)


class Review(models.Model):
    RATING_CHOICES = [
        (1, '1 Yıldız'),
        (2, '2 Yıldız'),
        (3, '3 Yıldız'),
        (4, '4 Yıldız'),
        (5, '5 Yıldız'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('product', 'user')
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.product.name} ({self.rating}/5)'
    
    @property
    def star_range(self):
        """Yıldız gösterimi için range döndürür"""
        return range(1, 6)


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlist_items')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.product.name}'


class Coupon(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Yüzde İndirim'),
        ('fixed', 'Sabit Tutar İndirim'),
        ('free_shipping', 'Ücretsiz Kargo'),
    ]
    
    USAGE_TYPES = [
        ('single', 'Tek Kullanım'),
        ('multiple', 'Çoklu Kullanım'),
        ('unlimited', 'Sınırsız Kullanım'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='Kupon Kodu')
    name = models.CharField(max_length=200, verbose_name='Kupon Adı')
    description = models.TextField(blank=True, verbose_name='Açıklama')
    
    discount_type = models.CharField(max_length=15, choices=DISCOUNT_TYPES, verbose_name='İndirim Türü')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='İndirim Değeri')
    
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Minimum Sipariş Tutarı')
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Maksimum İndirim Tutarı')
    
    usage_type = models.CharField(max_length=15, choices=USAGE_TYPES, default='single', verbose_name='Kullanım Türü')
    usage_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name='Kullanım Limiti')
    used_count = models.PositiveIntegerField(default=0, verbose_name='Kullanım Sayısı')
    
    valid_from = models.DateTimeField(verbose_name='Geçerlilik Başlangıcı')
    valid_until = models.DateTimeField(verbose_name='Geçerlilik Bitişi')
    
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # İsteğe bağlı: Belirli kategoriler için geçerli
    valid_categories = models.ManyToManyField(Category, blank=True, verbose_name='Geçerli Kategoriler')
    
    # İsteğe bağlı: Belirli kullanıcılar için geçerli
    valid_users = models.ManyToManyField(User, blank=True, verbose_name='Geçerli Kullanıcılar')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Kupon'
        verbose_name_plural = 'Kuponlar'
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def is_valid(self, user=None, order_amount=None):
        """Kuponun geçerli olup olmadığını kontrol eder"""
        from django.utils import timezone
        
        # Aktif mi?
        if not self.is_active:
            return False, "Kupon aktif değil"
        
        # ... existing code ...


class CouponUsage(models.Model):
    """Kupon kullanım geçmişi"""
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usage_history')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_usage')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='coupon_usage')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-used_at']
        verbose_name = 'Kupon Kullanımı'
        verbose_name_plural = 'Kupon Kullanımları'
    
    def __str__(self):
        return f"{self.user.username} - {self.coupon.code} - {self.used_at.strftime('%d.%m.%Y')}"


class StockAlert(models.Model):
    """Stok uyarısı sistemi"""
    STATUS_CHOICES = [
        ('active', 'Aktif'),
        ('notified', 'Bildirim Gönderildi'),
        ('cancelled', 'İptal Edildi'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stock_alerts')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_alerts')
    email = models.EmailField(verbose_name='E-posta Adresi')
    threshold = models.PositiveIntegerField(default=1, verbose_name='Stok Eşiği')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active', verbose_name='Durum')
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True, verbose_name='Bildirim Tarihi')
    
    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']
        verbose_name = 'Stok Uyarısı'
        verbose_name_plural = 'Stok Uyarıları'
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name} - {self.get_status_display()}"
    
    def send_notification(self):
        """Stok uyarısı bildirimi gönder"""
        from django.core.mail import send_mail
        from django.conf import settings
        from django.utils import timezone
        
        if self.status != 'active':
            return False
        
        subject = f"Stok Uyarısı: {self.product.name}"
        message = f"""
        Merhaba {self.user.get_full_name() or self.user.username},
        
        Takip ettiğiniz ürün tekrar stokta!
        
        Ürün: {self.product.name}
        Mevcut Stok: {self.product.stock}
        Fiyat: {self.product.price} TL
        
        Ürünü satın almak için sitemizi ziyaret edebilirsiniz.
        
        İyi alışverişler!
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.email],
                fail_silently=False,
            )
            
            # Durumu güncelle
            self.status = 'notified'
            self.notified_at = timezone.now()
            self.save()
            
            return True
        except Exception as e:
            print(f"Stok uyarısı e-postası gönderilemedi: {e}")
            return False


class ProductAttribute(models.Model):
    """
    Ürün özellik türleri (renk, beden, boyut vb.)
    """
    name = models.CharField(max_length=100, verbose_name='Özellik Adı')
    display_name = models.CharField(max_length=100, verbose_name='Görünen Ad')
    is_required = models.BooleanField(default=False, verbose_name='Zorunlu')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Ürün Özelliği'
        verbose_name_plural = 'Ürün Özellikleri'
    
    def __str__(self):
        return self.display_name


class ProductAttributeValue(models.Model):
    """
    Ürün özellik değerleri (kırmızı, mavi, S, M, L vb.)
    """
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100, verbose_name='Değer')
    display_value = models.CharField(max_length=100, verbose_name='Görünen Değer')
    color_code = models.CharField(max_length=7, blank=True, null=True, verbose_name='Renk Kodu', help_text='Renk için hex kodu (örn: #FF0000)')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sıralama')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    
    class Meta:
        ordering = ['attribute', 'sort_order', 'value']
        unique_together = ('attribute', 'value')
        verbose_name = 'Ürün Özellik Değeri'
        verbose_name_plural = 'Ürün Özellik Değerleri'
    
    def __str__(self):
        return f"{self.attribute.display_name}: {self.display_value}"


class ProductVariant(models.Model):
    """
    Ürün varyantları (ana ürünün farklı kombinasyonları)
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=100, unique=True, verbose_name='Stok Kodu')
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Fiyat')
    stock = models.PositiveIntegerField(default=0, verbose_name='Stok')
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Ağırlık (kg)')
    image = models.ImageField(upload_to='product_variants/', blank=True, null=True, verbose_name='Varyant Resmi')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['product', 'sku']
        verbose_name = 'Ürün Varyantı'
        verbose_name_plural = 'Ürün Varyantları'
    
    def __str__(self):
        return f"{self.product.name} - {self.sku}"
    
    @property
    def is_in_stock(self):
        return self.stock > 0
    
    @property
    def effective_price(self):
        """Varyant fiyatı varsa onu, yoksa ana ürün fiyatını döndür"""
        return self.price if self.price else self.product.price
    
    @property
    def variant_attributes(self):
        """Bu varyantın özelliklerini döndür"""
        return self.attribute_values.select_related('attribute_value__attribute')
    
    def get_attribute_display(self):
        """Varyant özelliklerini string olarak döndür"""
        attributes = []
        for variant_attr in self.variant_attributes:
            attributes.append(f"{variant_attr.attribute_value.attribute.display_name}: {variant_attr.attribute_value.display_value}")
        return ", ".join(attributes)


class ProductVariantAttribute(models.Model):
    """
    Ürün varyantı ve özellik değeri ilişkisi
    """
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='attribute_values')
    attribute_value = models.ForeignKey(ProductAttributeValue, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('variant', 'attribute_value')
        verbose_name = 'Varyant Özelliği'
        verbose_name_plural = 'Varyant Özellikleri'
    
    def __str__(self):
        return f"{self.variant.sku} - {self.attribute_value}"
