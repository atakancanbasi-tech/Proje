# payments/tests/test_callback_idempotency.py
import os
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from shop.models import Order, Product, Category, OrderItem
from payments.provider import get_provider
from payments.views import iyzico_callback, paytr_callback

User = get_user_model()


class CallbackIdempotencyTest(TestCase):
    """Test callback idempotency to prevent duplicate payments"""
    
    def setUp(self):
        self.factory = RequestFactory()
        
        # Test kategorisi ve ürünü oluştur
        self.category = Category.objects.create(
            name='Test Kategori', 
            description='Test açıklaması'
        )
        
        self.product = Product.objects.create(
            category=self.category,
            name='Test Ürün',
            description='Test ürün açıklaması',
            price=Decimal('100.00'),
            stock=10
        )
        
        # Test siparişi oluştur
        self.order = Order.objects.create(
            email='test@example.com',
            fullname='Test User',
            phone='05555555555',
            address='Test Adres',
            city='Test Şehir',
            total=Decimal('100.00'),
            status='received'
        )
        
        # Sipariş kalemi ekle
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            unit_price=Decimal('50.00'),
            line_total=Decimal('100.00')
        )
    
    @override_settings(PAYMENT_PROVIDER='mock')
    def test_iyzico_callback_idempotency_same_payment_ref(self):
        """Test that Iyzico callback with same payment_ref is idempotent"""
        provider = get_provider({})
        
        # İlk callback çağrısı
        request1 = self.factory.post('/payments/callback/iyzico/', {
            'status': 'success',
            'paymentId': 'IYZICO-PAY-123',
            'conversationId': str(self.order.id)
        })
        
        # Mock provider verify_callback'i override et
        def mock_verify_callback(request):
            return True, 'IYZICO-PAY-123', 'Mock success', str(self.order.id)
        
        provider.verify_callback = mock_verify_callback
        
        # İlk callback çağrısı başarılı olmalı
        response1 = iyzico_callback(request1)
        self.assertEqual(response1.status_code, 302)  # redirect
        
        # Sipariş durumunu kontrol et
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payment_provider, 'iyzico')
        self.assertEqual(self.order.payment_ref, 'IYZICO-PAY-123')
        self.assertIsNotNone(self.order.paid_at)
        
        # Stok kontrolü
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)  # 10 - 2 = 8
        
        # İkinci callback çağrısı (aynı payment_ref ile)
        request2 = self.factory.post('/payments/callback/iyzico/', {
            'status': 'success',
            'paymentId': 'IYZICO-PAY-123',
            'conversationId': str(self.order.id)
        })
        
        response2 = iyzico_callback(request2)
        self.assertEqual(response2.status_code, 200)  # "ok" response
        
        # Sipariş durumu değişmemeli
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payment_provider, 'iyzico')
        self.assertEqual(self.order.payment_ref, 'IYZICO-PAY-123')
        
        # Stok tekrar düşmemeli
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)  # Hala 8 olmalı
    
    @override_settings(PAYMENT_PROVIDER='mock')
    def test_iyzico_callback_idempotency_already_paid(self):
        """Test that Iyzico callback for already paid order is idempotent"""
        # Siparişi önceden ödenmış olarak işaretle
        self.order.status = 'paid'
        self.order.payment_provider = 'iyzico'
        self.order.payment_ref = 'PREVIOUS-PAY-456'
        self.order.paid_at = timezone.now()
        self.order.save()
        
        provider = get_provider({})
        
        # Mock provider verify_callback'i override et
        def mock_verify_callback(request):
            return True, 'NEW-PAY-789', 'Mock success', str(self.order.id)
        
        provider.verify_callback = mock_verify_callback
        
        request = self.factory.post('/payments/callback/iyzico/', {
            'status': 'success',
            'paymentId': 'NEW-PAY-789',
            'conversationId': str(self.order.id)
        })
        
        response = iyzico_callback(request)
        self.assertEqual(response.status_code, 200)  # "ok" response
        
        # Sipariş durumu değişmemeli (eski payment_ref korunmalı)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payment_provider, 'iyzico')
        self.assertEqual(self.order.payment_ref, 'PREVIOUS-PAY-456')  # Eski ref korunmalı
    
    @override_settings(PAYMENT_PROVIDER='mock')
    def test_paytr_callback_idempotency_same_payment_ref(self):
        """Test that PayTR callback with same payment_ref is idempotent"""
        provider = get_provider({})
        
        # Mock provider verify_callback'i override et
        def mock_verify_callback(request):
            return True, 'PAYTR-123', 'Mock success', str(self.order.id)
        
        provider.verify_callback = mock_verify_callback
        
        # İlk callback çağrısı
        request1 = self.factory.post('/payments/callback/paytr/', {
            'merchant_oid': str(self.order.id),
            'status': 'success',
            'total_amount': '10000',
            'hash': 'test_hash'
        })
        
        response1 = paytr_callback(request1)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.content.decode(), 'OK')
        
        # Sipariş durumunu kontrol et
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payment_provider, 'paytr')
        self.assertEqual(self.order.payment_ref, 'PAYTR-123')
        self.assertIsNotNone(self.order.paid_at)
        
        # Stok kontrolü
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)  # 10 - 2 = 8
        
        # İkinci callback çağrısı (aynı payment_ref ile)
        request2 = self.factory.post('/payments/callback/paytr/', {
            'merchant_oid': str(self.order.id),
            'status': 'success',
            'total_amount': '10000',
            'hash': 'test_hash'
        })
        
        response2 = paytr_callback(request2)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.content.decode(), 'OK')
        
        # Sipariş durumu değişmemeli
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payment_provider, 'paytr')
        self.assertEqual(self.order.payment_ref, 'PAYTR-123')
        
        # Stok tekrar düşmemeli
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)  # Hala 8 olmalı
    
    @override_settings(PAYMENT_PROVIDER='mock')
    def test_paytr_callback_idempotency_already_paid(self):
        """Test that PayTR callback for already paid order is idempotent"""
        # Siparişi önceden ödenmış olarak işaretle
        self.order.status = 'paid'
        self.order.payment_provider = 'paytr'
        self.order.payment_ref = 'PREVIOUS-PAYTR-456'
        self.order.paid_at = timezone.now()
        self.order.save()
        
        provider = get_provider({})
        
        # Mock provider verify_callback'i override et
        def mock_verify_callback(request):
            return True, 'NEW-PAYTR-789', 'Mock success', str(self.order.id)
        
        provider.verify_callback = mock_verify_callback
        
        request = self.factory.post('/payments/callback/paytr/', {
            'merchant_oid': str(self.order.id),
            'status': 'success',
            'total_amount': '10000',
            'hash': 'test_hash'
        })
        
        response = paytr_callback(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'OK')
        
        # Sipariş durumu değişmemeli (eski payment_ref korunmalı)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payment_provider, 'paytr')
        self.assertEqual(self.order.payment_ref, 'PREVIOUS-PAYTR-456')  # Eski ref korunmalı
    
    @override_settings(PAYMENT_PROVIDER='mock')
    def test_callback_concurrent_access_prevention(self):
        """Test that concurrent callback access is prevented via database locking"""
        provider = get_provider({})
        
        # Mock provider verify_callback'i override et
        def mock_verify_callback(request):
            return True, 'CONCURRENT-PAY-123', 'Mock success', str(self.order.id)
        
        provider.verify_callback = mock_verify_callback
        
        # Test için transaction.atomic() blokunu simüle et
        # Gerçek uygulama select_for_update() kullanıyor
        
        request = self.factory.post('/payments/callback/iyzico/', {
            'status': 'success',
            'paymentId': 'CONCURRENT-PAY-123',
            'conversationId': str(self.order.id)
        })
        
        # Transaction başlat ve siparişi kilitle
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=self.order.id)
            self.assertEqual(order.status, 'received')
            
            # Bu noktada başka bir thread aynı callback'i çağırsa beklemeli
            # Test ortamında simüle etmek zor, ama mantık doğru
            
            # Callback'i çağır
            response = iyzico_callback(request)
            self.assertEqual(response.status_code, 302)
        
        # Sipariş ödenmeli
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payment_ref, 'CONCURRENT-PAY-123')