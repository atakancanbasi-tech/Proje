from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import Address


class AddressBookTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_address_model_str(self):
        """Address model __str__ metodu testi"""
        address = Address.objects.create(
            user=self.user,
            title='Ev',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:1',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710'
        )
        
        self.assertEqual(str(address), 'Ev - İstanbul')

    def test_address_ordering(self):
        """Address model sıralama testi"""
        # Varsayılan olmayan adres
        address1 = Address.objects.create(
            user=self.user,
            title='Ofis',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:2',
            city='İstanbul',
            district='Beşiktaş',
            postal_code='34349',
            is_default=False
        )
        
        # Varsayılan adres
        address2 = Address.objects.create(
            user=self.user,
            title='Ev',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:1',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710',
            is_default=True
        )
        
        addresses = list(Address.objects.filter(user=self.user))
        # Varsayılan adres ilk sırada olmalı
        self.assertEqual(addresses[0], address2)
        self.assertEqual(addresses[1], address1)

    def test_multiple_default_addresses(self):
        """Birden fazla varsayılan adres testi"""
        # İlk varsayılan adres
        address1 = Address.objects.create(
            user=self.user,
            title='Ev',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:1',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710',
            is_default=True
        )
        
        # İkinci varsayılan adres (ilkini geçersiz kılmalı)
        address2 = Address.objects.create(
            user=self.user,
            title='Ofis',
            fullname='Test Kullanıcı',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:2',
            city='İstanbul',
            district='Beşiktaş',
            postal_code='34349',
            is_default=True
        )
        
        # İlk adres artık varsayılan olmamalı
        address1.refresh_from_db()
        self.assertFalse(address1.is_default)
        
        # İkinci adres varsayılan olmalı
        address2.refresh_from_db()
        self.assertTrue(address2.is_default)
        
        # Sadece bir varsayılan adres olmalı
        default_count = Address.objects.filter(user=self.user, is_default=True).count()
        self.assertEqual(default_count, 1)

    def test_address_user_isolation(self):
        """Kullanıcı izolasyonu testi"""
        # İkinci kullanıcı
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Her kullanıcı için adres oluştur
        address1 = Address.objects.create(
            user=self.user,
            title='Ev',
            fullname='Test Kullanıcı 1',
            phone='05551234567',
            address='Test Mahallesi Test Sokak No:1',
            city='İstanbul',
            district='Kadıköy',
            postal_code='34710',
            is_default=True
        )
        
        address2 = Address.objects.create(
            user=user2,
            title='Ev',
            fullname='Test Kullanıcı 2',
            phone='05551234568',
            address='Test Mahallesi Test Sokak No:2',
            city='Ankara',
            district='Çankaya',
            postal_code='06100',
            is_default=True
        )
        
        # Her kullanıcı sadece kendi adreslerini görmeli
        user1_addresses = Address.objects.filter(user=self.user)
        user2_addresses = Address.objects.filter(user=user2)
        
        self.assertEqual(user1_addresses.count(), 1)
        self.assertEqual(user2_addresses.count(), 1)
        self.assertEqual(user1_addresses.first(), address1)
        self.assertEqual(user2_addresses.first(), address2)

    def test_address_verbose_names(self):
        """Model verbose name testi"""
        self.assertEqual(Address._meta.verbose_name, 'Adres')
        self.assertEqual(Address._meta.verbose_name_plural, 'Adresler')

    def test_address_field_max_lengths(self):
        """Alan uzunluk testi"""
        # Maksimum uzunlukta değerler
        long_title = 'A' * 50
        long_fullname = 'B' * 100
        long_phone = 'C' * 20
        long_city = 'D' * 50
        long_district = 'E' * 50
        long_postal_code = 'F' * 10
        
        address = Address.objects.create(
            user=self.user,
            title=long_title,
            fullname=long_fullname,
            phone=long_phone,
            address='Test adres',
            city=long_city,
            district=long_district,
            postal_code=long_postal_code
        )
        
        self.assertEqual(address.title, long_title)
        self.assertEqual(address.fullname, long_fullname)
        self.assertEqual(address.phone, long_phone)
        self.assertEqual(address.city, long_city)
        self.assertEqual(address.district, long_district)
        self.assertEqual(address.postal_code, long_postal_code)