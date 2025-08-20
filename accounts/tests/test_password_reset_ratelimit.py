from django.test import TestCase


class PasswordResetRateLimitTests(TestCase):
    def test_password_reset_ratelimit(self):
        statuses = []
        for _ in range(6):
            resp = self.client.post('/accounts/password-reset/', {'email': 'ali@example.com'})
            statuses.append(resp.status_code)
        
        # İlk 5 deneme başarılı (200/302), 6.'sı engellenmeli (403/429)
        self.assertTrue(all(s in (200, 302) for s in statuses[:5]), statuses)
        self.assertIn(statuses[-1], (403, 429), statuses)