from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SignupVerifyTests(TestCase):

    def setUp(self):
        self.User = get_user_model()
        # Rate limiting cache'ini temizle
        cache.clear()
        # Mail outbox'ı temizle
        mail.outbox = []


    def test_verify_email_flow(self):

        # inaktif kullanıcı oluştur

        u = self.User.objects.create_user(

            username="mehmet", email="mehmet@example.com", password="sifre123", is_active=False

        )

        # doğrulama linki üret

        uidb64 = urlsafe_base64_encode(force_bytes(u.pk))

        token = default_token_generator.make_token(u)

        url = reverse("verify_email", args=[uidb64, token])

        # GET ile doğrula

        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)

        u.refresh_from_db()

        self.assertTrue(u.is_active)


    def test_resend_verification_ratelimit(self):

        # inaktif kullanıcı

        self.User.objects.create_user(

            username="ayse", email="ayse@example.com", password="sifre123", is_active=False

        )

        statuses = []

        for _ in range(6):  # 5 OK, 6. ratelimit

            resp = self.client.post(reverse("resend_verification"), {"email": "ayse@example.com"})

            statuses.append(resp.status_code)

        self.assertTrue(all(s in (200, 302) for s in statuses[:5]), statuses)

        self.assertIn(statuses[-1], (403, 429), statuses)


    def test_resend_verification_sends_mail(self):
        self.User.objects.create_user(
            username="veli", email="veli@example.com", password="sifre123", is_active=False
        )
        self.client.post(reverse("resend_verification"), {"email": "veli@example.com"})
        self.assertGreaterEqual(len(mail.outbox), 1)