from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.test import override_settings


class EmailVerificationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_active=False  # Başlangıçta aktif değil
        )
    
    def test_verify_email_success(self):
        """Geçerli token ile e-posta doğrulama testi"""
        # Token ve uidb64 oluştur
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        
        # Doğrulama URL'sine GET isteği gönder
        url = reverse('verify_email', args=[uidb64, token])
        response = self.client.get(url)
        
        # Başarılı doğrulama kontrolü
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tebrikler!')
        
        # Kullanıcının aktif olduğunu kontrol et
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
    
    def test_verify_email_invalid_token(self):
        """Geçersiz token ile e-posta doğrulama testi"""
        # Geçersiz token
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_token = 'invalid-token'
        
        # Doğrulama URL'sine GET isteği gönder
        url = reverse('verify_email', args=[uidb64, invalid_token])
        response = self.client.get(url)
        
        # Başarısız doğrulama kontrolü
        self.assertEqual(response.status_code, 400)
        self.assertIn('Doğrulama Başarısız', response.content.decode())
        
        # Kullanıcının hala aktif olmadığını kontrol et
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
    
    def test_verify_email_invalid_uid(self):
        """Geçersiz UID ile e-posta doğrulama testi"""
        # Geçersiz UID
        invalid_uidb64 = 'invalid-uid'
        token = default_token_generator.make_token(self.user)
        
        # Doğrulama URL'sine GET isteği gönder
        url = reverse('verify_email', args=[invalid_uidb64, token])
        response = self.client.get(url)
        
        # Başarısız doğrulama kontrolü
        self.assertEqual(response.status_code, 400)
        self.assertIn('Doğrulama Başarısız', response.content.decode())
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_resend_verification_email(self):
        """E-posta yeniden gönderme testi"""
        # POST isteği gönder
        url = reverse('resend_verification')
        response = self.client.post(url, {'email': self.user.email})
        
        # Başarılı yanıt kontrolü
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'E-posta Gönderildi')
        
        # E-posta gönderildiğini kontrol et
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn('E-posta doğrulama', sent_email.subject)
        self.assertEqual(sent_email.to, [self.user.email])
    
    def test_resend_verification_nonexistent_email(self):
        """Var olmayan e-posta ile yeniden gönderme testi"""
        # POST isteği gönder
        url = reverse('resend_verification')
        response = self.client.post(url, {'email': 'nonexistent@example.com'})
        
        # Güvenlik nedeniyle yine başarılı yanıt döner
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'E-posta Gönderildi')
    
    def test_resend_verification_empty_email(self):
        """Boş e-posta ile yeniden gönderme testi"""
        # POST isteği gönder
        url = reverse('resend_verification')
        response = self.client.post(url, {'email': ''})
        
        # Hata yanıtı kontrolü
        self.assertEqual(response.status_code, 400)
        self.assertIn('E-posta gerekli', response.content.decode())
    
    def test_resend_verification_already_active_user(self):
        """Zaten aktif kullanıcı için yeniden gönderme testi"""
        # Kullanıcıyı aktif yap
        self.user.is_active = True
        self.user.save()
        
        # POST isteği gönder
        url = reverse('resend_verification')
        response = self.client.post(url, {'email': self.user.email})
        
        # Başarılı yanıt kontrolü (idempotent davranış)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'E-posta Gönderildi')