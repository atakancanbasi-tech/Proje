from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
import json

from shop.models import Product, Category, Order
from shop.shipping import calc_shipping, get_shipping_methods
from accounts.models import Address


class ShippingTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Test Kategori'
        )
        self.product = Product.objects.create(
            name='Test Ürün',
            category=self.category,
            price=Decimal('100.00'),
            stock=10
        )

    def test_calc_shipping_standard(self):
        """Standart kargo hesaplama testi"""
        shipping_fee = calc_shipping(100.0, 'standard')
        self.assertEqual(shipping_fee, 49.9)

    def test_calc_shipping_express(self):
        """Hızlı kargo hesaplama testi"""
        shipping_fee = calc_shipping(100.0, 'express')
        self.assertEqual(shipping_fee, 99.9)

    def test_calc_shipping_free_threshold(self):
        """Ücretsiz kargo eşiği testi"""
        shipping_fee = calc_shipping(600.0, 'standard')
        self.assertEqual(shipping_fee, 0.0)

    def test_get_shipping_methods(self):
        """Kargo yöntemleri listesi testi"""
        methods = get_shipping_methods()
        self.assertEqual(len(methods), 2)
        self.assertEqual(methods[0], ('standard', 'Standart Kargo', 49.9))
        self.assertEqual(methods[1], ('express', 'Hızlı Kargo', 99.9))


class AddressTestCase(TestCase):
    def setUp(self):
        self.client = Client()
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
            category=self.category,
            price=Decimal('100.00'),
            stock=10
        )
        self.category = Category.objects.create(
            name='Test Kategori'
        )
        self.product = Product.objects.create(
            name='Test Ürün',
            category=self.category,
            price=Decimal('100.00'),
            stock=10
        )

    def test_checkout_with_shipping(self):
        """Kargo seçimi ile checkout testi"""
        # Sepete ürün ekle
        self.client.post(reverse('shop:add_to_cart', args=[self.product.id]), {
            'quantity': 1
        })
        
        # Checkout sayfasını kontrol et
        response = self.client.get(reverse('shop:checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Standart Kargo')
        self.assertContains(response, 'Hızlı Kargo')

    def test_ajax_totals_calculation(self):
        """AJAX toplam hesaplama testi"""
        # Sepete ürün ekle
        self.client.post(reverse('shop:add_to_cart', args=[self.product.id]), {
            'quantity': 1
        })
        
        # AJAX ile toplam hesapla
        response = self.client.post(
            reverse('shop:calculate_totals_ajax'),
            json.dumps({'shipping_method': 'standard'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['totals']['subtotal'], 100.0)
        self.assertEqual(data['totals']['shipping_fee'], 49.9)
        self.assertEqual(data['totals']['total'], 149.9)


class AddressTestCase(TestCase):
    def setUp(self):
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
            category=self.category,
            price=Decimal('100.00'),
            stock=10
        )

    def test_address_creation(self):
        """Adres oluşturma testi"""
        address = Address.objects.create(
            user=self.user,
            title='Ev',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:1',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710',
            is_default=True
        )
        
        self.assertEqual(address.user, self.user)
        self.assertEqual(address.title, 'Ev')
        self.assertTrue(address.is_default)

    def test_default_address_logic(self):
        """Varsayılan adres mantığı testi"""
        # İlk adres
        address1 = Address.objects.create(
            user=self.user,
            title='Ev',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:1',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710',
            is_default=True
        )
        
        # İkinci adres (varsayılan)
        address2 = Address.objects.create(
            user=self.user,
            title='Ofis',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:2',
            city='İstanbul',
            district='Beşiktaş',
            postal_code='34349',
            is_default=True
        )
        
        # İlk adresin varsayılan olmaktan çıkması gerekir
        address1.refresh_from_db()
        self.assertFalse(address1.is_default)
        self.assertTrue(address2.is_default)

    def test_checkout_with_saved_address(self):
        """Kayıtlı adres ile checkout testi"""
        # Kullanıcı girişi yap
        self.client.login(username='testuser', password='testpass123')
        
        # Sepete ürün ekle
        self.client.post(reverse('shop:add_to_cart', args=[self.product.id]), {
            'quantity': 1
        })
        
        # Adres oluştur
        address = Address.objects.create(
            user=self.user,
            title='Ev',
            fullname='Test Kullanıcı',
            address='Test Mahallesi Test Sokak No:1',
            phone='05551234567',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710',
            is_default=True
        )
        
        # Checkout sayfasını kontrol et
        response = self.client.get(reverse('shop:checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, address.title)
        self.assertContains(response, address.fullname)