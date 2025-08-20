from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from shop.models import Order, Product, Category
from decimal import Decimal

User = get_user_model()

class BillingInfoTests(TestCase):

    def setUp(self):
        # Basit bir sepet durumu varsayın; varsa helper kullanabilirsiniz.
        self.category = Category.objects.create(name="Test Kategori")
        self.product = Product.objects.create(
            name="Test Ürün",
            category=self.category,
            price=Decimal('100.00'),
            stock=10
        )
        
        # Test kullanıcı oluştur
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Kullanıcı girişi yap
        self.client.login(username='testuser', password='testpass123')
        
        # Sepete ürün ekle
        self.client.post(reverse('shop:add_to_cart', kwargs={'product_id': self.product.id}), {
            'quantity': 1
        })


    def test_bireysel_tckn_flow(self):
        # Session'a checkout_data yaz
        session = self.client.session
        session['checkout_data'] = {
            'fullname': 'Ali Veli',
            'email': 'ali@example.com',
            'phone': '05551234567',
            'address': 'Adres 1',
            'city': 'İstanbul',
            'district': 'Kadıköy',
            'postal_code': '34700',
            'shipping_method': 'standard',
            'billing': {
                'want_invoice': True,
                'invoice_type': 'bireysel',
                'billing_fullname': 'Ali Veli',
                'tckn': '12345678901',
                'e_archive_email': 'ali@example.com',
                'billing_address': 'Adres 1',
                'billing_city': 'İstanbul',
                'billing_district': 'Kadıköy',
                'billing_postcode': '34700',
                'kvkk_approved': True,
            }
        }
        session.save()
        
        resp = self.client.post(reverse('shop:checkout_pay'), {})
        self.assertIn(resp.status_code, (200, 302))
        
        order = Order.objects.last()
        self.assertIsNotNone(order)
        self.assertEqual(order.invoice_type, 'bireysel')
        self.assertEqual(order.tckn, '12345678901')
        self.assertEqual(order.vkn, '')


    def test_kurumsal_vkn_flow(self):
        session = self.client.session
        session['checkout_data'] = {
            'fullname': 'Örnek A.Ş.',
            'email': 'finans@example.com',
            'phone': '05551234567',
            'address': 'Adres 2',
            'city': 'Ankara',
            'district': 'Çankaya',
            'postal_code': '06500',
            'shipping_method': 'standard',
            'billing': {
                'want_invoice': True,
                'invoice_type': 'kurumsal',
                'billing_fullname': 'Örnek A.Ş.',
                'vkn': '1234567890',
                'tax_office': 'Kozyatağı',
                'e_archive_email': 'finans@example.com',
                'billing_address': 'Adres 2',
                'billing_city': 'Ankara',
                'billing_district': 'Çankaya',
                'billing_postcode': '06500',
                'kvkk_approved': True,
            }
        }
        session.save()
        
        resp = self.client.post(reverse('shop:checkout_pay'), {})
        self.assertIn(resp.status_code, (200, 302))
        
        order = Order.objects.last()
        self.assertIsNotNone(order)
        self.assertEqual(order.invoice_type, 'kurumsal')
        self.assertEqual(order.vkn, '1234567890')
        self.assertEqual(order.tckn, '')

    def test_no_invoice_flow(self):
        """Fatura istenmediğinde fatura alanlarının boş kalması"""
        session = self.client.session
        session['checkout_data'] = {
            'fullname': 'Fatura İstemiyor',
            'email': 'noinvoice@example.com',
            'phone': '05551234567',
            'address': 'Adres 3',
            'city': 'İzmir',
            'district': 'Karşıyaka',
            'postal_code': '35500',
            'shipping_method': 'standard',
            'billing': {
                'want_invoice': False,
            }
        }
        session.save()
        
        resp = self.client.post(reverse('shop:checkout_pay'), {})
        self.assertIn(resp.status_code, (200, 302))
        
        order = Order.objects.last()
        self.assertIsNotNone(order)
        # want_invoice=False olduğunda vergi kimlik alanları boş kalmalı
        self.assertEqual(order.tckn, '')
        self.assertEqual(order.vkn, '')
        # invoice_type için uygulama varsayılanı kullanılabilir; bu nedenle burada kontrol etmiyoruz