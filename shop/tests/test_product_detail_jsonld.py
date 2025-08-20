from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from shop.models import Product, Category


class ProductDetailJSONLDTestCase(TestCase):
    def setUp(self):
        """Test için gerekli verileri oluştur"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.category = Category.objects.create(
            name='Test Kategori'
        )
        
        self.product = Product.objects.create(
            name='Test Ürün',
            description='Bu bir test ürünüdür.',
            price=99.99,
            stock=10,
            category=self.category
        )
    
    def test_product_detail_page_loads(self):
        """Ürün detay sayfasının yüklendiğini test et"""
        url = reverse('shop:product_detail', kwargs={'pk': self.product.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
    
    def test_product_jsonld_structure(self):
        """Product JSON-LD yapısının doğru olduğunu test et"""
        url = reverse('shop:product_detail', kwargs={'pk': self.product.pk})
        response = self.client.get(url)
        
        # Debug kodu kaldırıldı
        
        # JSON-LD script etiketinin varlığını kontrol et
        self.assertContains(response, 'application/ld+json')
        
        # Gerekli JSON-LD alanlarını kontrol et
        self.assertContains(response, '"@type": "Product"')
        self.assertContains(response, '"priceCurrency": "TRY"')
        self.assertContains(response, self.product.name)
        # Fiyat formatını kontrol et (Türkiye yerel ayarlarında virgül kullanılır)
        self.assertContains(response, '99,99')  # Türkiye formatında virgül kullanılır
        
        # Schema.org URL'lerini kontrol et
        self.assertContains(response, 'https://schema.org')
    
    def test_product_jsonld_with_stock_status(self):
        """Stok durumuna göre JSON-LD availability alanını test et"""
        # Stokta olan ürün
        url = reverse('shop:product_detail', kwargs={'pk': self.product.pk})
        response = self.client.get(url)
        self.assertContains(response, 'https://schema.org/InStock')
        
        # Stokta olmayan ürün
        self.product.stock = 0
        self.product.save()
        response = self.client.get(url)
        self.assertContains(response, 'https://schema.org/OutOfStock')
    
    def test_breadcrumb_navigation(self):
        """Breadcrumb navigasyonunu test et"""
        url = reverse('shop:product_detail', kwargs={'pk': self.product.pk})
        response = self.client.get(url)
        
        # Breadcrumb yapısını kontrol et
        self.assertContains(response, 'aria-label="İçerik yolu"')
        self.assertContains(response, 'breadcrumb')
        self.assertContains(response, 'Ürünler')
        self.assertContains(response, self.product.name)
    
    def test_related_products_section(self):
        """İlgili ürünler bölümünü test et"""
        # Aynı kategoride başka bir ürün oluştur
        related_product = Product.objects.create(
            name='İlgili Test Ürün',
            description='Bu ilgili bir test ürünüdür.',
            price=149.99,
            stock=5,
            category=self.category
        )
        
        url = reverse('shop:product_detail', kwargs={'pk': self.product.pk})
        response = self.client.get(url)
        
        # İlgili ürünler bölümünün varlığını kontrol et
        self.assertContains(response, 'Benzer Ürünler')
        self.assertContains(response, related_product.name)
        self.assertContains(response, 'İncele')