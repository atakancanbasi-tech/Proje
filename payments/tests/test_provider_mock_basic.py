from django.test import TestCase, override_settings
from payments.provider import get_provider, MockProvider


class MockProviderBasicTests(TestCase):
    @override_settings(PAYMENT_PROVIDER="mock")
    def test_get_provider_returns_mock(self):
        provider = get_provider(self.settings)
        self.assertIsInstance(provider, MockProvider)

    @override_settings(PAYMENT_PROVIDER="mock")
    def test_mock_charge_returns_success_and_ref(self):
        provider = get_provider(self.settings)
        result = provider.charge(amount=100.0, currency="TRY", order_ref="ORD123")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.provider_ref)
        self.assertTrue(str(result.provider_ref).startswith("MOCK-"))

    @override_settings(PAYMENT_PROVIDER="mock")
    def test_mock_verify_callback_tuple(self):
        provider = get_provider(self.settings)
        ok, provider_ref, message, order_ref = provider.verify_callback(None)
        self.assertTrue(ok)
        self.assertIsNone(provider_ref)
        self.assertIsNone(order_ref)
        self.assertIn("Mock", (message or ""))