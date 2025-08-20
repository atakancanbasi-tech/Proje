from django.test import TestCase
from shop.forms import BillingForm


class BillingFormValidationExtraTests(TestCase):
    def test_bireysel_gecerli_tckn_11_hane(self):
        form = BillingForm(data={
            "want_invoice": True,
            "invoice_type": "bireysel",
            "billing_fullname": "Ali Veli",
            "tckn": "12345678901",  # 11 hane, sadece rakam
            "kvkk_approved": True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_kurumsal_gecerli_vkn_10_hane(self):
        form = BillingForm(data={
            "want_invoice": True,
            "invoice_type": "kurumsal",
            "billing_fullname": "Örnek A.Ş.",
            "vkn": "1234567890",  # 10 hane, sadece rakam
            "tax_office": "Kozyatağı",
            "kvkk_approved": True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_bireysel_gecersiz_tckn(self):
        form = BillingForm(data={
            "want_invoice": True,
            "invoice_type": "bireysel",
            "billing_fullname": "Ali Veli",
            "tckn": "12AB567",  # hatalı format
            "kvkk_approved": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("tckn", form.errors)

    def test_kurumsal_gecersiz_vkn(self):
        form = BillingForm(data={
            "want_invoice": True,
            "invoice_type": "kurumsal",
            "billing_fullname": "Örnek A.Ş.",
            "vkn": "12345ABC",  # hatalı format
            "tax_office": "Kozyatağı",
            "kvkk_approved": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("vkn", form.errors)