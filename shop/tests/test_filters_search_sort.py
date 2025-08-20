from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from ..models import Product, Category


class FiltersSearchSortTestCase(TestCase):
    """Filtreleme, arama ve sıralama testleri"""
    
    def setUp(self):
        """Test verilerini hazırla"""
        self.client = Client()
        
        # Kategoriler oluştur
        self.category1 = Category.objects.create(name='Elektronik')
        self.category2 = Category.objects.create(name='Giyim')
        
        # 20 ürün oluştur
        self.products = []
        for i in range(20):
            category = self.category1 if i % 2 == 0 else self.category2
            price = Decimal('10.00') + Decimal(str(i * 5))  # 10, 15, 20, 25, ..., 105
            
            product = Product.objects.create(
                name=f'Ürün {i+1}',
                description=f'Bu {i+1}. ürünün açıklaması',
                price=price,
                stock=10 if i < 15 else 0,  # İlk 15 ürün stokta
                category=category
            )
            self.products.append(product)
    
    def test_text_search_icontains(self):
        """Metin arama testi - icontains eşleşmesi"""
        # 'Ürün 1' araması - 'Ürün 1', 'Ürün 10', 'Ürün 11', ... eşleşmeli
        response = self.client.get(reverse('shop:product_list'), {'q': 'Ürün 1'})
        self.assertEqual(response.status_code, 200)
        
        # Sonuçları kontrol et
        products = response.context['products']
        product_names = [p.name for p in products]
        
        # 'Ürün 1' içeren ürünler olmalı
        expected_names = ['Ürün 1', 'Ürün 10', 'Ürün 11', 'Ürün 12', 'Ürün 13', 'Ürün 14', 'Ürün 15', 'Ürün 16', 'Ürün 17', 'Ürün 18', 'Ürün 19']
        for name in expected_names:
            self.assertIn(name, product_names)
    
    def test_price_range_filter(self):
        """Fiyat aralığı filtresi testi"""
        # 20-50 TL arasındaki ürünler
        response = self.client.get(reverse('shop:product_list'), {
            'min_price': '20',
            'max_price': '50'
        })
        self.assertEqual(response.status_code, 200)
        
        products = response.context['products']
        
        # Fiyatları kontrol et
        for product in products:
            self.assertGreaterEqual(product.price, Decimal('20.00'))
            self.assertLessEqual(product.price, Decimal('50.00'))
        
        # Beklenen ürün sayısı (fiyatı 20-50 arasında olanlar)
        expected_count = len([p for p in self.products if Decimal('20.00') <= p.price <= Decimal('50.00')])
        self.assertEqual(len(products), expected_count)
    
    def test_category_filter(self):
        """Kategori filtresi testi"""
        # Sadece Elektronik kategorisi
        response = self.client.get(reverse('shop:product_list'), {
            'category': str(self.category1.id)
        })
        self.assertEqual(response.status_code, 200)
        
        products = response.context['products']
        
        # Tüm ürünler Elektronik kategorisinde olmalı
        for product in products:
            self.assertEqual(product.category, self.category1)
        
        # Beklenen ürün sayısı (çift indeksli ürünler)
        expected_count = len([p for p in self.products if p.category == self.category1])
        self.assertEqual(len(products), expected_count)
    
    def test_sort_price_asc(self):
        """Fiyat artan sıralama testi"""
        response = self.client.get(reverse('shop:product_list'), {
            'sort': 'price_asc'
        })
        self.assertEqual(response.status_code, 200)
        
        products = list(response.context['products'])
        
        # İlk ürün en düşük fiyatlı olmalı
        self.assertEqual(products[0].price, Decimal('10.00'))
        
        # Fiyatlar artan sırada olmalı
        prices = [p.price for p in products]
        self.assertEqual(prices, sorted(prices))
    
    def test_sort_price_desc(self):
        """Fiyat azalan sıralama testi"""
        response = self.client.get(reverse('shop:product_list'), {
            'sort': 'price_desc'
        })
        self.assertEqual(response.status_code, 200)
        
        products = list(response.context['products'])
        
        # İlk ürün en yüksek fiyatlı olmalı
        self.assertEqual(products[0].price, Decimal('105.00'))
        
        # Fiyatlar azalan sırada olmalı
        prices = [p.price for p in products]
        self.assertEqual(prices, sorted(prices, reverse=True))
    
    def test_sort_new_default(self):
        """Yeni ürünler sıralaması (varsayılan) testi"""
        response = self.client.get(reverse('shop:product_list'), {
            'sort': 'new'
        })
        self.assertEqual(response.status_code, 200)
        
        products = list(response.context['products'])
        
        # En son eklenen ürün ilk sırada olmalı (en yüksek ID)
        self.assertEqual(products[0].name, 'Ürün 20')
        
        # ID'ler azalan sırada olmalı (yeni ürünler önce)
        ids = [p.id for p in products]
        self.assertEqual(ids, sorted(ids, reverse=True))
    
    def test_price_validation_negative_values(self):
        """Negatif fiyat değerleri normalizasyon testi"""
        response = self.client.get(reverse('shop:product_list'), {
            'min_price': '-10',
            'max_price': '50'
        })
        self.assertEqual(response.status_code, 200)
        
        # Negatif değer 0'a normalize edilmeli
        self.assertEqual(response.context['min_price'], '0')
        self.assertEqual(response.context['max_price'], '50.0')
    
    def test_price_validation_reverse_range(self):
        """Ters fiyat aralığı normalizasyon testi"""
        response = self.client.get(reverse('shop:product_list'), {
            'min_price': '50',
            'max_price': '20'
        })
        self.assertEqual(response.status_code, 200)
        
        # Değerler yer değiştirmeli
        self.assertEqual(response.context['min_price'], '20.0')
        self.assertEqual(response.context['max_price'], '50.0')
    
    def test_combined_filters(self):
        """Birleşik filtreler testi"""
        response = self.client.get(reverse('shop:product_list'), {
            'q': 'Ürün',
            'category': str(self.category1.id),
            'min_price': '20',
            'max_price': '60',
            'sort': 'price_asc'
        })
        self.assertEqual(response.status_code, 200)
        
        products = list(response.context['products'])
        
        # Tüm filtreler uygulanmalı
        for product in products:
            self.assertIn('Ürün', product.name)
            self.assertEqual(product.category, self.category1)
            self.assertGreaterEqual(product.price, Decimal('20.00'))
            self.assertLessEqual(product.price, Decimal('60.00'))
        
        # Fiyat sıralaması korunmalı
        if len(products) > 1:
            prices = [p.price for p in products]
            self.assertEqual(prices, sorted(prices))
    
    def test_pagination_preserves_query_string(self):
        """Sayfalama query string koruma testi"""
        response = self.client.get(reverse('shop:product_list'), {
            'q': 'Ürün',
            'sort': 'price_asc',
            'page': '1'
        })
        self.assertEqual(response.status_code, 200)
        
        # Sayfalama bağlamı mevcut olmalı
        self.assertIn('page_obj', response.context)
        
        # Query parametreleri korunmalı
        self.assertEqual(response.context['q'], 'Ürün')
        self.assertEqual(response.context['sort_by'], 'price_asc')
    
    def test_seo_canonical_and_noindex(self):
        """SEO canonical URL ve noindex meta testi"""
        # Filtre olmadan (canonical URL)
        response = self.client.get(reverse('shop:product_list'))
        self.assertEqual(response.status_code, 200)
        
        # Filtre ile (noindex)
        response = self.client.get(reverse('shop:product_list'), {'q': 'test'})
        self.assertEqual(response.status_code, 200)
        
        # Template'te noindex meta etiketi olmalı
        self.assertContains(response, 'name="robots" content="noindex,follow"')
        self.assertContains(response, 'rel="canonical"')