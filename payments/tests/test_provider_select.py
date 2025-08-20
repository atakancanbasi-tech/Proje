from django.test import TestCase, override_settings
from payments.provider import get_provider, MockProvider, IyzicoProvider, PayTRProvider


class ProviderSelectionTest(TestCase):
    """Test payment provider selection based on settings"""
    
    @override_settings(PAYMENT_PROVIDER='mock')
    def test_get_mock_provider(self):
        """Test that mock provider is returned when PAYMENT_PROVIDER=mock"""
        provider = get_provider()
        self.assertIsInstance(provider, MockProvider)
    
    @override_settings(PAYMENT_PROVIDER='iyzico')
    def test_get_iyzico_provider(self):
        """Test that Iyzico provider is returned when PAYMENT_PROVIDER=iyzico"""
        provider = get_provider()
        self.assertIsInstance(provider, IyzicoProvider)
    
    @override_settings(PAYMENT_PROVIDER='paytr')
    def test_get_paytr_provider(self):
        """Test that PayTR provider is returned when PAYMENT_PROVIDER=paytr"""
        provider = get_provider()
        self.assertIsInstance(provider, PayTRProvider)
    
    @override_settings(PAYMENT_PROVIDER='invalid')
    def test_get_provider_with_invalid_setting(self):
        """Test that mock provider is returned for invalid PAYMENT_PROVIDER"""
        provider = get_provider()
        self.assertIsInstance(provider, MockProvider)
    
    def test_get_provider_without_setting(self):
        """Test that mock provider is returned when PAYMENT_PROVIDER is not set"""
        # Remove PAYMENT_PROVIDER setting if it exists
        from django.conf import settings
        if hasattr(settings, 'PAYMENT_PROVIDER'):
            delattr(settings, 'PAYMENT_PROVIDER')
        
        provider = get_provider()
        self.assertIsInstance(provider, MockProvider)
    
    @override_settings(PAYMENT_PROVIDER='MOCK')  # Test case insensitivity
    def test_get_provider_case_insensitive(self):
        """Test that provider selection is case insensitive"""
        provider = get_provider()
        self.assertIsInstance(provider, MockProvider)