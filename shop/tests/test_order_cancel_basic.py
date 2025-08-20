from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from shop.models import Order, OrderItem, Product, Category


class OrderCancelBasicTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="ali", email="ali@example.com", password="sifre12345"
        )
        self.cat = Category.objects.create(name="Genel")
        self.product = Product.objects.create(
            name="Kalem", price=Decimal("10.00"), stock=5, category=self.cat
        )

    def test_cancel_received_order_restores_stock(self):
        # received sipariş + 2 adet ürün
        order = Order.objects.create(
            fullname="Ali Veli",
            email="ali@example.com",
            address="Adres",
            city="İstanbul",
            status="received",
            total=Decimal("20.00"),
            user=self.user,
        )
        OrderItem.objects.create(order=order, product=self.product, unit_price=Decimal("10.00"), quantity=2, line_total=Decimal("20.00"))

        self.client.login(username="ali", password="sifre12345")
        url = reverse("order_cancel", args=[order.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)  # OK response

        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, "cancelled")
        # 5 + 2 = 7
        self.assertEqual(self.product.stock, 7)