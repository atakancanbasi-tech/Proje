from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from decimal import Decimal
from shop.models import Product, Category, Order, OrderItem
from shop.cart import Cart
import sys
import logging

# Logging ayarla
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

User = get_user_model()


class OrderCreationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Kategori oluştur
        self.category = Category.objects.create(
            name='Test Kategori'
        )
        
        # Ürün oluştur
        self.product = Product.objects.create(
            name='Test Ürün',
            category=self.category,
            price=Decimal('100.00'),
            stock=5,
            description='Test ürün açıklaması'
        )
        
        # Kullanıcı girişi yap
        self.client.login(username='testuser', password='testpass123')
        
    def test_order_creation_flow(self):
        """Sipariş oluşturma akışını test et"""
        # E-posta kutusunu temizle
        mail.outbox.clear()
        # Ürünü sepete ekle
        response = self.client.post(reverse('shop:add_to_cart', kwargs={'product_id': self.product.id}), {
            'quantity': 1
        })
        self.assertEqual(response.status_code, 302)
        
        # Checkout sayfasına git
        response = self.client.get(reverse('shop:checkout'))
        self.assertEqual(response.status_code, 200)
        
        # Session'a checkout_data'yı manuel olarak kaydet
        checkout_data = {
            'fullname': 'Test Kullanıcı',
            'email': 'test@example.com',
            'phone': '05551234567',
            'address': 'Test Adres',
            'city': 'İstanbul',
            'district': 'Kadıköy',
            'postal_code': '34000'
        }
        
        # Session'a manuel olarak kaydet
        session = self.client.session
        session['checkout_data'] = checkout_data
        session.save()
        
        # Ödeme işlemini gerçekleştir
        response = self.client.post(reverse('shop:checkout_pay'), {})
        
        # Başarılı ödeme sonrası yönlendirme kontrolü
        self.assertEqual(response.status_code, 302)
        
        # Debug: Session'daki checkout_data'yı kontrol et
        session = self.client.session
        
        # Debug bilgisini exception ile göster
        if not response.url.endswith(reverse('shop:checkout_success')):
            raise Exception(f"Response URL: {response.url}, Expected: {reverse('shop:checkout_success')}, Session data: {session.get('checkout_data')}")
        
        self.assertTrue(response.url.endswith(reverse('shop:checkout_success')))
        
        # Veritabanı kontrolü
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        
        order = Order.objects.first()
        self.assertEqual(order.fullname, 'Test Kullanıcı')
        self.assertEqual(order.email, 'test@example.com')
        self.assertEqual(order.total, Decimal('149.90'))  # 100.00 + 49.90 kargo
        self.assertEqual(order.status, 'paid')
        
        order_item = OrderItem.objects.first()
        self.assertEqual(order_item.product, self.product)
        self.assertEqual(order_item.quantity, 1)
        self.assertEqual(order_item.unit_price, Decimal('100.00'))
        self.assertEqual(order_item.line_total, Decimal('100.00'))
        
        # Stok kontrolü
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        
        # E-posta kontrolü (sipariş onayı + durum bildirimi)
        self.assertEqual(len(mail.outbox), 2)
        email = mail.outbox[0]
        self.assertIn('Ödemeniz onaylandı', email.subject)
        self.assertIn('test@example.com', email.to)
        
    def test_insufficient_stock(self):
        """Yetersiz stok durumunu test et"""
        # E-posta kutusunu temizle
        mail.outbox.clear()
        # Stoku 0 yap
        self.product.stock = 0
        self.product.save()
        
        # Ürünü sepete ekle
        response = self.client.post(reverse('shop:add_to_cart', kwargs={'product_id': self.product.id}), {
            'quantity': 1
        })
        
        # Ödeme işlemini gerçekleştir
        checkout_data = {
            'fullname': 'Test Kullanıcı',
            'email': 'test@example.com',
            'phone': '05551234567',
            'address': 'Test Adres',
            'city': 'İstanbul',
            'district': 'Kadıköy',
            'postal_code': '34000'
        }
        
        response = self.client.post(reverse('shop:checkout_pay'), checkout_data)
        
        # Hata durumunda checkout sayfasına geri dönmeli
        # veya hata mesajı ile birlikte aynı sayfada kalmalı
        # Bu durumda sipariş oluşturulmamış olmalı
        
        # Sipariş oluşturulmamış olmalı
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        
        # E-posta gönderilmemiş olmalı
        self.assertEqual(len(mail.outbox), 0)