from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from shop.models import Category, Product, Order, OrderItem
from decimal import Decimal


class TurkishSmokeTests(TestCase):
    """Türkçe yerelleştirme ve temel işlevsellik duman testleri"""
    
    def setUp(self):
        """Test verilerini hazırla"""
        self.client = Client()
        
        # Test kategorisi oluştur
        self.category = Category.objects.create(
            name="Test Kategorisi",
            description="Test açıklaması"
        )
        
        # Test ürünü oluştur
        self.product = Product.objects.create(
            name="Test Ürünü",
            description="Test ürün açıklaması",
            price=Decimal('99.99'),
            stock=10,
            category=self.category
        )
        
        # Test kullanıcısı oluştur
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_anasayfa_yonlendirmesi(self):
        """Ana sayfa yönlendirmesini test et"""
        response = self.client.get('/shop/')
        self.assertIn(response.status_code, [301, 302])
        self.assertTrue(
            response.url.endswith('/shop/products/') or 
            response.url.endswith('/shop/products')
        )
    
    def test_urun_listesi_sayfasi(self):
        """Ürün listesi sayfasının çalıştığını test et"""
        response = self.client.get(reverse('shop:product_list'))
        self.assertEqual(response.status_code, 200)
        
        # Türkçe içerik kontrolü
        content = response.content.decode('utf-8')
        self.assertIn('Ürünler', content)
        self.assertIn('₺', content)  # Türk Lirası sembolü
    
    def test_urun_detay_sayfasi(self):
        """Ürün detay sayfasının çalıştığını test et"""
        response = self.client.get(
            reverse('shop:product_detail', kwargs={'pk': self.product.pk})
        )
        self.assertEqual(response.status_code, 200)
        
        # Türkçe içerik kontrolü
        content = response.content.decode('utf-8')
        self.assertIn('Sepete Ekle', content)
        self.assertIn('₺', content)
        self.assertIn(self.product.name, content)
    
    def test_sepet_sayfasi(self):
        """Sepet sayfasının çalıştığını test et"""
        response = self.client.get(reverse('shop:cart_detail'))
        self.assertEqual(response.status_code, 200)
        
        # Türkçe içerik kontrolü
        content = response.content.decode('utf-8')
        self.assertIn('Sepet', content)
        self.assertIn('₺', content)
    
    def test_sepete_urun_ekleme(self):
        """Sepete ürün ekleme işlemini test et"""
        response = self.client.post(
            reverse('shop:add_to_cart', kwargs={'product_id': self.product.pk})
        )
        self.assertIn(response.status_code, [200, 302])
        
        # Sepet sayfasına yönlendirme kontrolü
        if response.status_code == 302:
            self.assertTrue(
                response.url.endswith('/shop/cart/') or
                response.url.endswith('/shop/cart')
            )
    
    def test_giris_yapmamis_kullanici_siparisler(self):
        """Giriş yapmamış kullanıcının siparişler sayfasına erişimini test et"""
        response = self.client.get(reverse('shop:my_orders'))
        self.assertIn(response.status_code, [302, 200])
        
        if response.status_code == 302:
            # Login sayfasına yönlendirme bekleniyor
            self.assertTrue('login' in response.url)
    
    def test_giris_yapmis_kullanici_siparisler(self):
        """Giriş yapmış kullanıcının siparişler sayfasına erişimini test et"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('shop:my_orders'))
        self.assertEqual(response.status_code, 200)
        
        # Türkçe içerik kontrolü
        content = response.content.decode('utf-8')
        self.assertIn('Siparişler', content)
    
    def test_arama_sayfasi(self):
        """Arama sayfasının çalıştığını test et"""
        response = self.client.get(
            reverse('shop:product_list') + '?q=test'
        )
        self.assertEqual(response.status_code, 200)
        
        # Türkçe içerik kontrolü
        content = response.content.decode('utf-8')
        self.assertIn('₺', content)
    
    def test_kategori_filtreleme(self):
        """Kategori filtreleme işlemini test et"""
        response = self.client.get(
            reverse('shop:product_list') + f'?category={self.category.id}'
        )
        self.assertEqual(response.status_code, 200)
        
        # Türkçe içerik kontrolü
        content = response.content.decode('utf-8')
        self.assertIn('₺', content)
        self.assertIn(self.category.name, content)
    
    def test_gelismis_arama_sayfasi(self):
        """Gelişmiş arama sayfasının çalıştığını test et"""
        response = self.client.get(reverse('shop:advanced_search'))
        self.assertEqual(response.status_code, 200)
        
        # Türkçe içerik kontrolü
        content = response.content.decode('utf-8')
        self.assertIn('Arama', content)
        self.assertIn('₺', content)
    
    def test_ajax_arama_onerileri(self):
        """AJAX arama önerilerini test et"""
        response = self.client.get(
            reverse('shop:search_autocomplete') + '?q=test',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')