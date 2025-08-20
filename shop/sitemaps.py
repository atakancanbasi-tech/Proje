from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product


class ProductSitemap(Sitemap):
    """Ürünler için sitemap"""
    changefreq = 'daily'
    priority = 0.8
    
    def items(self):
        """Aktif ürünleri döndür"""
        return Product.objects.filter(stock__gt=0).select_related('category')
    
    def lastmod(self, obj):
        """Son değişiklik tarihi"""
        # created_at varsa onu kullan, yoksa None döndür
        return getattr(obj, 'updated_at', getattr(obj, 'created_at', None))
    
    def location(self, obj):
        """Ürün detay URL'i"""
        return reverse('shop:product_detail', args=[obj.pk])