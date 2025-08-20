from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core import mail
from django.template.loader import render_to_string
from decimal import Decimal
from unittest.mock import patch

from shop.models import Product, Category, Order, OrderItem
from shop.views.cart import checkout_pay
from django.test import Client
from django.urls import reverse


class OrderEmailHTMLTestCase(TestCase):
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
        self.order = Order.objects.create(
            user=self.user,
            email='test@example.com',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:1',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710',
            shipping_method='standard',
            shipping_fee=Decimal('49.90'),
            total=Decimal('149.90'),
            status='paid'
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )

    def test_email_template_rendering(self):
        """E-posta template'inin doğru render edilmesi testi"""
        email_context = {
            'order': self.order,
            'order_items': self.order.items.all(),
            'subtotal': Decimal('100.00'),
            'shipping_fee': Decimal('49.90'),
            'total': Decimal('149.90'),
            'shipping_method_display': 'Standart Kargo'
        }
        
        html_content = render_to_string('email/order_confirmation.html', email_context)
        
        # HTML içeriğinin temel elementlerini kontrol et
        self.assertIn('Sipariş Onayı', html_content)
        self.assertIn(self.order.number, html_content)
        self.assertIn(self.order.fullname, html_content)
        self.assertIn(self.order.email, html_content)
        self.assertIn(self.product.name, html_content)
        self.assertIn('100,00', html_content)  # Ürün fiyatı
        self.assertIn('49,90', html_content)   # Kargo ücreti
        self.assertIn('149,90', html_content)  # Toplam
        self.assertIn('Standart Kargo', html_content)
        self.assertIn(self.order.address, html_content)
        self.assertIn(self.order.city, html_content)
        self.assertIn(self.order.district, html_content)

    def test_email_template_structure(self):
        """E-posta template'inin HTML yapısı testi"""
        email_context = {
            'order': self.order,
            'order_items': self.order.items.all(),
            'subtotal': Decimal('100.00'),
            'shipping_fee': Decimal('15.00'),
            'total': Decimal('115.00'),
            'shipping_method_display': 'Standart Kargo'
        }
        
        html_content = render_to_string('email/order_confirmation.html', email_context)
        
        # HTML yapısının temel elementlerini kontrol et
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<html lang="tr">', html_content)
        self.assertIn('<head>', html_content)
        self.assertIn('<body>', html_content)
        self.assertIn('<table class="order-items">', html_content)
        self.assertIn('<div class="totals">', html_content)
        self.assertIn('<div class="address">', html_content)

    def test_free_shipping_display(self):
        """Ücretsiz kargo gösterimi testi"""
        # Ücretsiz kargo ile sipariş
        free_order = Order.objects.create(
            user=self.user,
            email='test@example.com',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:1',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710',
            shipping_method='standard',
            shipping_fee=Decimal('0.00'),
            total=Decimal('500.00'),
            status='paid'
        )
        
        email_context = {
            'order': free_order,
            'order_items': [],
            'subtotal': Decimal('500.00'),
            'shipping_fee': Decimal('0.00'),
            'total': Decimal('500.00'),
            'shipping_method_display': 'Standart Kargo'
        }
        
        html_content = render_to_string('email/order_confirmation.html', email_context)
        
        # Ücretsiz kargo yazısının görünmesi
        self.assertIn('ÜCRETSİZ', html_content)

    def test_express_shipping_display(self):
        """Hızlı kargo gösterimi testi"""
        email_context = {
            'order': self.order,
            'order_items': self.order.items.all(),
            'subtotal': Decimal('100.00'),
            'shipping_fee': Decimal('99.90'),
            'total': Decimal('199.90'),
            'shipping_method_display': 'Hızlı Kargo'
        }
        
        html_content = render_to_string('email/order_confirmation.html', email_context)
        
        # Hızlı kargo yazısının görünmesi
        self.assertIn('Hızlı Kargo', html_content)
        self.assertIn('99,90', html_content)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_sending_integration(self):
        """E-posta gönderimi entegrasyon testi"""
        from django.core import mail
        from django.core.mail import EmailMultiAlternatives
        mail.outbox = []  # E-posta kutusunu temizle
        from django.template.loader import render_to_string
        from django.conf import settings
        
        # E-posta içeriği hazırla
        email_context = {
            'order': self.order,
            'order_items': self.order.items.all(),
            'subtotal': Decimal('100.00'),
            'shipping_fee': Decimal('15.00'),
            'total': Decimal('115.00'),
            'shipping_method_display': 'Standart Kargo'
        }
        
        # HTML ve text içerik oluştur
        html_content = render_to_string('email/order_confirmation.html', email_context)
        text_content = f"""Sipariş Onayı
        
Sayın {self.order.fullname},
        
Siparişiniz başarıyla alınmıştır.
Sipariş No: {self.order.number}
Toplam Tutar: 149.90 TL
        
Teşekkür ederiz.
        """
        
        # E-posta gönder
        subject = f'Sipariş Onayı - {self.order.number}'
        from_email = 'test@example.com'
        to_email = [self.order.email]
        
        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        # E-posta gönderildiğini kontrol et
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        
        self.assertEqual(sent_email.subject, subject)
        self.assertEqual(sent_email.to, to_email)
        self.assertEqual(sent_email.from_email, from_email)
        
        # HTML alternatifi olduğunu kontrol et
        self.assertEqual(len(sent_email.alternatives), 1)
        html_alternative = sent_email.alternatives[0]
        self.assertEqual(html_alternative[1], 'text/html')
        self.assertIn('Sipariş Onayı', html_alternative[0])

    def test_multiple_order_items_display(self):
        """Birden fazla ürün gösterimi testi"""
        # İkinci ürün ekle
        product2 = Product.objects.create(
            name='Test Ürün 2',
            category=self.category,
            price=Decimal('50.00'),
            stock=5
        )
        
        order_item2 = OrderItem.objects.create(
            order=self.order,
            product=product2,
            quantity=2,
            unit_price=Decimal('50.00'),
            line_total=Decimal('100.00')
        )
        
        email_context = {
            'order': self.order,
            'order_items': self.order.items.all(),
            'subtotal': Decimal('200.00'),
            'shipping_fee': Decimal('49.90'),
            'total': Decimal('249.90'),
            'shipping_method_display': 'Standart Kargo'
        }
        
        html_content = render_to_string('email/order_confirmation.html', email_context)
        
        # Her iki ürünün de görünmesi
        self.assertIn(self.product.name, html_content)
        self.assertIn(product2.name, html_content)
        self.assertIn('249,90', html_content)  # Yeni toplam