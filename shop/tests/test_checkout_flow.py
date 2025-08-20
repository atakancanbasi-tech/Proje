from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class CheckoutFlowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_checkout_success_page(self):
        """Checkout success sayfasının yüklendiğini test et"""
        response = self.client.get(reverse('shop:checkout_success'))
        self.assertEqual(response.status_code, 200)

    def test_checkout_fail_page(self):
        """Checkout fail sayfasının yüklendiğini test et"""
        response = self.client.get(reverse('shop:checkout_fail'))
        self.assertEqual(response.status_code, 200)

    def test_empty_cart_checkout(self):
        """Boş sepet ile ödeme yapmaya çalışıldığında test et"""
        response = self.client.post(reverse('shop:checkout_pay'))
        self.assertRedirects(response, reverse('shop:cart_detail'))

    def test_checkout_page_loads(self):
        """Checkout sayfasının yüklendiğini test et"""
        response = self.client.get(reverse('shop:checkout'))
        # Boş sepet ile checkout sayfasına gidildiğinde cart sayfasına yönlendirilir
        self.assertEqual(response.status_code, 302)