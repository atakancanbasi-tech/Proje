from django.test import TestCase
from shop.forms import BillingForm


class BillingFormValidationTests(TestCase):
    def test_bireysel_icin_tckn_11_hane_ve_rakam_olmali(self):
        form = BillingForm(data={
            "want_invoice": True,
            "invoice_type": "bireysel",
            "billing_fullname": "Ali Veli",
            "tckn": "12AB567",  # geçersiz: hem kısa hem harf içeriyor
            "kvkk_approved": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("tckn", form.errors)

        form2 = BillingForm(data={
            "want_invoice": True,
            "invoice_type": "bireysel",
            "billing_fullname": "Ali Veli",
            "tckn": "1234567890",  # geçersiz: 10 hane
            "kvkk_approved": True,
        })
        self.assertFalse(form2.is_valid())
        self.assertIn("tckn", form2.errors)

    def test_kurumsal_icin_vkn_10_hane_ve_rakam_olmali(self):
        form = BillingForm(data={
            "want_invoice": True,
            "invoice_type": "kurumsal",
            "billing_fullname": "Örnek A.Ş.",
            "vkn": "12345ABC",  # geçersiz
            "tax_office": "Kozyatağı",
            "kvkk_approved": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("vkn", form.errors)

        form2 = BillingForm(data={
            "want_invoice": True,
            "invoice_type": "kurumsal",
            "billing_fullname": "Örnek A.Ş.",
            "vkn": "123456789",  # geçersiz: 9 hane
            "tax_office": "Kozyatağı",
            "kvkk_approved": True,
        })
        self.assertFalse(form2.is_valid())
        self.assertIn("vkn", form2.errors)