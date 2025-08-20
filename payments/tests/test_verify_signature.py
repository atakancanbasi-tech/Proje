import os
from django.test import TestCase, RequestFactory
from django.conf import settings
from unittest import skipUnless
from payments.provider import IyzicoProvider, PayTRProvider


class SignatureVerificationTest(TestCase):
    """Test payment provider signature verification"""
    
    def setUp(self):
        self.factory = RequestFactory()
    
    @skipUnless(
        os.getenv('IYZICO_API_KEY') and os.getenv('IYZICO_SECRET'),
        "Iyzico sandbox keys not configured"
    )
    def test_iyzico_verify_callback_with_wrong_signature(self):
        """Test that Iyzico callback verification fails with wrong signature"""
        provider = IyzicoProvider(settings)
        
        # Create a mock request with wrong signature
        request = self.factory.post('/payments/callback/iyzico/', {
            'status': 'success',
            'paymentId': 'test-payment-id',
            'conversationId': 'ORDER-123',
            'mdStatus': '1',
            # Wrong signature
            'hash': 'wrong_signature_hash'
        })
        
        ok, provider_ref, message, order_ref = provider.verify_callback(request)
        
        self.assertFalse(ok)
        self.assertIsNone(provider_ref)
        self.assertIn('İmza geçersiz', message or '')
    
    @skipUnless(
        os.getenv('PAYTR_MERCHANT_ID') and os.getenv('PAYTR_MERCHANT_KEY') and os.getenv('PAYTR_MERCHANT_SALT'),
        "PayTR sandbox keys not configured"
    )
    def test_paytr_verify_callback_with_wrong_signature(self):
        """Test that PayTR callback verification fails with wrong signature"""
        provider = PayTRProvider(settings)
        
        # Create a mock request with wrong signature
        request = self.factory.post('/payments/callback/paytr/', {
            'merchant_oid': 'ORDER-123',
            'status': 'success',
            'total_amount': '10000',  # 100.00 TL in kuruş
            'payment_type': 'card',
            # Wrong signature
            'hash': 'wrong_signature_hash'
        })
        
        ok, provider_ref, message, order_ref = provider.verify_callback(request)
        
        self.assertFalse(ok)
        self.assertIsNone(provider_ref)
        self.assertIn('İmza geçersiz', message or '')
    
    def test_iyzico_verify_callback_without_keys(self):
        """Test Iyzico callback verification without API keys"""
        # Temporarily remove environment variables
        original_api_key = os.environ.get('IYZICO_API_KEY')
        original_secret = os.environ.get('IYZICO_SECRET')
        
        if 'IYZICO_API_KEY' in os.environ:
            del os.environ['IYZICO_API_KEY']
        if 'IYZICO_SECRET' in os.environ:
            del os.environ['IYZICO_SECRET']
        
        try:
            provider = IyzicoProvider(settings)
            
            request = self.factory.post('/payments/callback/iyzico/', {
                'status': 'success',
                'paymentId': 'test-payment-id',
                'conversationId': 'ORDER-123',
                'hash': 'any_hash'
            })
            
            ok, provider_ref, message, order_ref = provider.verify_callback(request)
            
            self.assertFalse(ok)
            self.assertIsNone(provider_ref)
            self.assertIn('konfigürasyon', message.lower() if message else '')
            
        finally:
            # Restore environment variables
            if original_api_key:
                os.environ['IYZICO_API_KEY'] = original_api_key
            if original_secret:
                os.environ['IYZICO_SECRET'] = original_secret
    
    def test_paytr_verify_callback_without_keys(self):
        """Test PayTR callback verification without merchant keys"""
        # Temporarily remove environment variables
        original_merchant_id = os.environ.get('PAYTR_MERCHANT_ID')
        original_merchant_key = os.environ.get('PAYTR_MERCHANT_KEY')
        original_merchant_salt = os.environ.get('PAYTR_MERCHANT_SALT')
        
        for key in ['PAYTR_MERCHANT_ID', 'PAYTR_MERCHANT_KEY', 'PAYTR_MERCHANT_SALT']:
            if key in os.environ:
                del os.environ[key]
        
        try:
            provider = PayTRProvider(settings)
            
            request = self.factory.post('/payments/callback/paytr/', {
                'merchant_oid': 'ORDER-123',
                'status': 'success',
                'total_amount': '10000',
                'hash': 'any_hash'
            })
            
            ok, provider_ref, message, order_ref = provider.verify_callback(request)
            
            self.assertFalse(ok)
            self.assertIsNone(provider_ref)
            self.assertIn('konfigürasyon', message.lower() if message else '')
            
        finally:
            # Restore environment variables
            if original_merchant_id:
                os.environ['PAYTR_MERCHANT_ID'] = original_merchant_id
            if original_merchant_key:
                os.environ['PAYTR_MERCHANT_KEY'] = original_merchant_key
            if original_merchant_salt:
                os.environ['PAYTR_MERCHANT_SALT'] = original_merchant_salt
    
    def test_paytr_verify_callback_missing_fields(self):
        """Test PayTR callback verification with missing required fields"""
        provider = PayTRProvider(settings)
        
        # Create a request missing required fields
        request = self.factory.post('/payments/callback/paytr/', {
            'merchant_oid': 'ORDER-123',
            # Missing status, total_amount, hash
        })
        
        ok, provider_ref, message, order_ref = provider.verify_callback(request)
        
        self.assertFalse(ok)
        self.assertIsNone(provider_ref)
        self.assertIsNotNone(message)
    
    def test_iyzico_verify_callback_missing_fields(self):
        """Test Iyzico callback verification with missing required fields"""
        provider = IyzicoProvider(settings)
        
        # Create a request missing required fields
        request = self.factory.post('/payments/callback/iyzico/', {
            'conversationId': 'ORDER-123',
            # Missing status, paymentId, hash
        })
        
        ok, provider_ref, message, order_ref = provider.verify_callback(request)
        
        self.assertFalse(ok)
        self.assertIsNone(provider_ref)
        self.assertIsNotNone(message)