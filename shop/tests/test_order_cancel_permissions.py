from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from shop.models import Product, Order, OrderItem, Category


class OrderCancelPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pw")
        self.other = User.objects.create_user(username="other", password="pw")
        self.staff = User.objects.create_user(username="staff", password="pw", is_staff=True)
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(name="P", price=10, stock=5, category=self.category)
        self.order = Order.objects.create(user=self.owner, status="received", total=10)
        OrderItem.objects.create(order=self.order, product=self.product, quantity=2, unit_price=10, line_total=20)

    def _cancel_url(self, order_id):
        # Yol adı projeye göre değişebiliyor; path sabitini kullanalım
        return f"/orders/{order_id}/cancel/"

    def test_owner_can_cancel(self):
        self.client.login(username="owner", password="pw")
        resp = self.client.post(self._cancel_url(self.order.id))
        self.assertIn(resp.status_code, (200, 302))

    def test_other_user_forbidden(self):
        self.client.login(username="other", password="pw")
        resp = self.client.post(self._cancel_url(self.order.id))
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_cancel(self):
        self.client.login(username="staff", password="pw")
        resp = self.client.post(self._cancel_url(self.order.id))
        self.assertIn(resp.status_code, (200, 302))