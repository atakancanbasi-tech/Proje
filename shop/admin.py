from django.contrib import admin
from django.contrib import messages
from .models import Category, Product, Review, ShippingCompany, PaymentMethod, Order, OrderItem, OrderStatusHistory, Wishlist, Coupon, CouponUsage, StockAlert, ProductAttribute, ProductAttributeValue, ProductVariant, ProductVariantAttribute
from .utils import send_order_status_update_email

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ('sku', 'price', 'stock', 'weight', 'is_active')
    readonly_fields = ('created_at',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "average_rating", "review_count", "variant_count")
    list_filter = ("category",)
    search_fields = ("name", "description")
    inlines = [ProductVariantInline]
    
    def average_rating(self, obj):
        return f"{obj.average_rating:.1f}" if obj.average_rating else "0.0"
    average_rating.short_description = "Ortalama Puan"
    
    def review_count(self, obj):
        return obj.review_count
    review_count.short_description = "Yorum Sayısı"
    
    def variant_count(self, obj):
        return obj.variants.count()
    variant_count.short_description = "Varyant Sayısı"

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'created_at', 'is_approved']
    list_filter = ['rating', 'is_approved', 'created_at']
    search_fields = ['product__name', 'user__username', 'comment']
    list_editable = ['is_approved']
    readonly_fields = ['created_at']
    actions = ['approve_reviews', 'disapprove_reviews']
    
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} yorum onaylandı.')
    approve_reviews.short_description = 'Seçili yorumları onayla'
    
    def disapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} yorumun onayı kaldırıldı.')
    disapprove_reviews.short_description = 'Seçili yorumların onayını kaldır'

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    fields = ('from_status', 'to_status', 'changed_by', 'created_at', 'note')
    readonly_fields = ('from_status', 'to_status', 'changed_by', 'created_at', 'note')

@admin.register(ShippingCompany)
class ShippingCompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'base_price', 'price_per_kg', 'free_shipping_threshold', 'estimated_delivery_days', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    list_editable = ['is_active', 'base_price', 'price_per_kg']


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'payment_type', 'processing_fee_percentage', 'min_amount', 'max_amount', 'is_active']
    list_filter = ['payment_type', 'is_active']
    search_fields = ['name']
    list_editable = ['is_active', 'processing_fee_percentage']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id','number','fullname','total','status','invoice_type','payment_provider','payment_ref','created_at','paid_at')
    search_fields = ('id','fullname','email','payment_ref','tckn','vkn','billing_fullname','tax_office')
    list_filter = ('status','invoice_type','payment_provider','created_at')
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    def number(self, obj):
        return obj.number
    number.short_description = 'Sipariş No'

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order','product','quantity','unit_price','line_total')


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'from_status', 'to_status', 'changed_by', 'created_at')
    list_filter = ('from_status', 'to_status', 'created_at')
    search_fields = ('order__id', 'order__email', 'note')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    def has_add_permission(self, request):
        # Manuel eklemeyi engelle, sadece sistem tarafından oluşturulsun
        return False
    
    def has_change_permission(self, request, obj=None):
        # Değiştirmeyi engelle, sadece görüntüleme
        return False


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at', 'product__category']
    search_fields = ['user__username', 'user__email', 'product__name']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'discount_type', 'discount_value', 'usage_type', 'used_count', 'is_active', 'valid_from', 'valid_until']
    list_filter = ['discount_type', 'usage_type', 'is_active', 'valid_from', 'valid_until']
    search_fields = ['code', 'name', 'description']
    list_editable = ['is_active']
    readonly_fields = ['used_count', 'created_at', 'updated_at']
    filter_horizontal = ['valid_categories', 'valid_users']
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('code', 'name', 'description', 'is_active')
        }),
        ('İndirim Ayarları', {
            'fields': ('discount_type', 'discount_value', 'min_order_amount', 'max_discount_amount')
        }),
        ('Kullanım Ayarları', {
            'fields': ('usage_type', 'usage_limit', 'used_count')
        }),
        ('Geçerlilik Tarihleri', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Kısıtlamalar', {
            'fields': ('valid_categories', 'valid_users'),
            'classes': ('collapse',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('valid_categories', 'valid_users')


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['coupon', 'user', 'order', 'discount_amount', 'used_at']
    list_filter = ['used_at', 'coupon__discount_type']
    search_fields = ['coupon__code', 'user__username', 'order__id']
    readonly_fields = ['used_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('coupon', 'user', 'order')


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'email', 'threshold', 'status', 'created_at', 'notified_at')
    list_filter = ('status', 'created_at', 'notified_at')
    search_fields = ('user__username', 'user__email', 'product__name', 'email')
    readonly_fields = ('created_at', 'notified_at')
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('user', 'product', 'email', 'threshold')
        }),
        ('Durum', {
            'fields': ('status', 'created_at', 'notified_at')
        }),
    )
    
    actions = ['send_notifications', 'mark_as_cancelled']
    
    def send_notifications(self, request, queryset):
        """Seçili stok uyarıları için bildirim gönder"""
        sent_count = 0
        for alert in queryset.filter(status='active'):
            if alert.product.stock >= alert.threshold:
                if alert.send_notification():
                    sent_count += 1
        
        if sent_count > 0:
            messages.success(request, f'{sent_count} stok uyarısı bildirimi gönderildi.')
        else:
            messages.warning(request, 'Hiçbir bildirim gönderilemedi.')
    
    send_notifications.short_description = "Seçili uyarılar için bildirim gönder"
    
    def mark_as_cancelled(self, request, queryset):
        """Seçili stok uyarılarını iptal et"""
        updated = queryset.update(status='cancelled')
        messages.success(request, f'{updated} stok uyarısı iptal edildi.')
    
    mark_as_cancelled.short_description = "Seçili uyarıları iptal et"


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 1
    fields = ('value', 'display_value', 'color_code', 'sort_order', 'is_active')


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'is_required', 'is_active', 'created_at')
    list_filter = ('is_required', 'is_active', 'created_at')
    search_fields = ('name', 'display_name')
    list_editable = ('is_required', 'is_active')
    readonly_fields = ('created_at',)
    inlines = [ProductAttributeValueInline]


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ('attribute', 'display_value', 'value', 'color_code', 'sort_order', 'is_active')
    list_filter = ('attribute', 'is_active')
    search_fields = ('value', 'display_value', 'attribute__name')
    list_editable = ('sort_order', 'is_active')
    ordering = ('attribute', 'sort_order', 'value')


class ProductVariantAttributeInline(admin.TabularInline):
    model = ProductVariantAttribute
    extra = 1
    autocomplete_fields = ('attribute_value',)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product', 'get_attribute_display', 'effective_price', 'stock', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'product__category')
    search_fields = ('sku', 'product__name')
    list_editable = ('stock', 'is_active')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ProductVariantAttributeInline]
    autocomplete_fields = ('product',)
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('product', 'sku', 'is_active')
        }),
        ('Özellikler', {
            'fields': ('attributes',)
        }),
        ('Fiyat ve Stok', {
            'fields': ('price', 'stock', 'weight')
        }),
        ('Görsel', {
            'fields': ('image',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_attribute_display(self, obj):
        return ", ".join([f"{a.attribute.display_name}: {a.attribute_value.display_value}" for a in obj.variant_attributes.select_related('attribute_value__attribute').all()])
    get_attribute_display.short_description = 'Özellikler'
    
    def effective_price(self, obj):
        return obj.price
    effective_price.short_description = 'Geçerli Fiyat'
