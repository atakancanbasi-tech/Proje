from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from payments import get_provider

class PaymentMockTest(TestCase):
    def test_get_provider_mock(self):
        self.assertEqual(get_provider(settings).__class__.__name__, "MockProvider")