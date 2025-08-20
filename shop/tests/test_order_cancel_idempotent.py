from django.test import TestCase
from django.contrib.auth import get_user_model
from shop.models import Product, Order, OrderItem, Category


class OrderCancelIdempotentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.u = User.objects.create_user(username="u", password="pw")
        self.category = Category.objects.create(name="Test Category")
        self.p = Product.objects.create(name="P", price=10, stock=5, category=self.category)
        self.o = Order.objects.create(user=self.u, status="received", total=10)
        OrderItem.objects.create(order=self.o, product=self.p, quantity=2, unit_price=10, line_total=20)

    def _cancel(self):
        return self.client.post(f"/orders/{self.o.id}/cancel/")

    def test_double_cancel_restock_once(self):
        self.client.login(username="u", password="pw")
        # İlk iptal
        r1 = self._cancel()
        self.assertIn(r1.status_code, (200, 302))
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 7)  # 5 + 2
        # İkinci iptal denemesi (idempotent)
        r2 = self._cancel()
        self.assertIn(r2.status_code, (200, 302))  # nazik cevap, ikinci kez stok artmaz
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 7)