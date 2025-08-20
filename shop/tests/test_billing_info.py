from django.test import TestCase
from django.urls import reverse
from shop.models import Order, Product, Category

class BillingInfoBasicTests(TestCase):
    
    def setUp(self):
        # Test için kategori ve ürün oluştur
        self.category = Category.objects.create(name="Test Kategori")
        self.product = Product.objects.create(
            name="Test Ürün",
            category=self.category,
            price=100.00,
            stock=10
        )
    
    def test_checkout_contains_billing_fields(self):
        # Sepete ürün ekle
        self.client.post(reverse("shop:add_to_cart", args=[self.product.id]), {
            'quantity': 1
        })
        
        resp = self.client.get(reverse("shop:checkout"))
        # Yeni alan isimlerine göre kontrol
        self.assertContains(resp, 'name="invoice_type"')
        self.assertContains(resp, 'name="tckn"')
        self.assertContains(resp, 'name="vkn"')
        self.assertContains(resp, 'name="billing_fullname"')
        self.assertContains(resp, 'name="tax_office"')
        self.assertContains(resp, 'name="e_archive_email"')
        self.assertContains(resp, 'name="billing_address"')
        self.assertContains(resp, 'name="billing_city"')
        self.assertContains(resp, 'name="billing_district"')
        self.assertContains(resp, 'name="billing_postcode"')
        self.assertContains(resp, 'name="kvkk_approved"')
    
    def test_order_model_has_fields(self):
        field_names = {f.name for f in Order._meta.get_fields()}
        for expected in {
            "invoice_type","billing_fullname","tckn","vkn",
            "tax_office","e_archive_email","billing_address",
            "billing_city","billing_district","billing_postcode","kvkk_approved"
        }:
            self.assertIn(expected, field_names)