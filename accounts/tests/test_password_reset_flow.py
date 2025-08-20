from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetFlowTests(TestCase):
    def test_password_reset_sends_email(self):
        User = get_user_model()
        User.objects.create_user(username='ali', email='ali@example.com', password='sifre12345')
        resp = self.client.post('/accounts/password-reset/', {'email': 'ali@example.com'})
        self.assertIn(resp.status_code, (200, 302))
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertIn('Şifre', mail.outbox[0].subject)