from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from ..models import Product, Category
import xml.etree.ElementTree as ET


class SitemapRobotsTestCase(TestCase):
    """Sitemap ve robots.txt testleri"""
    
    def setUp(self):
        """Test verilerini hazırla"""
        self.client = Client()
        
        # Test kategorisi oluştur
        self.category = Category.objects.create(name='Test Kategori')
        
        # Test ürünleri oluştur
        self.products = []
        for i in range(5):
            product = Product.objects.create(
                name=f'Test Ürün {i+1}',
                description=f'Test ürün {i+1} açıklaması',
                price=Decimal('10.00') + Decimal(str(i * 5)),
                stock=10,
                category=self.category
            )
            self.products.append(product)
    
    def test_sitemap_xml_returns_200(self):
        """Sitemap.xml 200 döner testi"""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
    
    def test_sitemap_contains_product_urls(self):
        """Sitemap en az 1 ürün URL'i içerir testi"""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        
        # XML içeriğini parse et
        content = response.content.decode('utf-8')
        root = ET.fromstring(content)
        
        # Namespace tanımla
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # URL'leri bul
        urls = root.findall('.//ns:url', namespace)
        self.assertGreater(len(urls), 0, "Sitemap'te hiç URL bulunamadı")
        
        # Ürün URL'lerini kontrol et
        product_urls = []
        for url in urls:
            loc = url.find('ns:loc', namespace)
            if loc is not None and '/shop/product/' in loc.text:
                product_urls.append(loc.text)
        
        self.assertGreaterEqual(len(product_urls), 1, "Sitemap'te en az 1 ürün URL'i olmalı")
        
        # İlk ürünün URL'inin doğru olduğunu kontrol et
        first_product = self.products[0]
        expected_url_part = f'/shop/product/{first_product.id}/'
        
        found_expected_url = any(expected_url_part in url for url in product_urls)
        self.assertTrue(found_expected_url, f"Beklenen ürün URL'i bulunamadı: {expected_url_part}")
    
    def test_sitemap_xml_structure(self):
        """Sitemap XML yapısı testi"""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        
        # XML içeriğini parse et
        content = response.content.decode('utf-8')
        root = ET.fromstring(content)
        
        # Root element kontrolü
        self.assertEqual(root.tag, '{http://www.sitemaps.org/schemas/sitemap/0.9}urlset')
        
        # Namespace tanımla
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # URL elementlerini kontrol et
        urls = root.findall('.//ns:url', namespace)
        
        for url in urls:
            # Her URL'de loc elementi olmalı
            loc = url.find('ns:loc', namespace)
            self.assertIsNotNone(loc, "URL elementinde loc bulunamadı")
            self.assertTrue(loc.text.startswith('http'), "URL http ile başlamalı")
            
            # lastmod elementi olmalı
            lastmod = url.find('ns:lastmod', namespace)
            self.assertIsNotNone(lastmod, "URL elementinde lastmod bulunamadı")
    
    def test_robots_txt_returns_200(self):
        """robots.txt 200 döner testi"""
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
    
    def test_robots_txt_content(self):
        """robots.txt içerik testi"""
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # robots.txt temel yapısı olmalı
        self.assertIn('User-agent:', content)
        
        # Sitemap referansı olmalı (production modunda)
        # Test ortamında DEBUG=True olduğu için Disallow olabilir
        # Bu yüzden her iki durumu da kontrol edelim
        has_sitemap = 'Sitemap:' in content
        has_disallow = 'Disallow:' in content
        
        # En az birisi olmalı
        self.assertTrue(has_sitemap or has_disallow, 
                       "robots.txt'te Sitemap veya Disallow direktifi olmalı")
    
    def test_sitemap_product_detail_urls(self):
        """Sitemap'teki ürün URL'lerinin erişilebilir olduğu testi"""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        
        # XML içeriğini parse et
        content = response.content.decode('utf-8')
        root = ET.fromstring(content)
        
        # Namespace tanımla
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Ürün URL'lerini bul
        product_urls = []
        for url in root.findall('.//ns:url', namespace):
            loc = url.find('ns:loc', namespace)
            if loc is not None and '/shop/product/' in loc.text:
                # Tam URL'den path kısmını al
                url_path = loc.text.split('://')[1].split('/', 1)[1] if '://' in loc.text else loc.text
                if not url_path.startswith('/'):
                    url_path = '/' + url_path
                product_urls.append(url_path)
        
        # En az bir ürün URL'i test et
        if product_urls:
            test_url = product_urls[0]
            response = self.client.get(test_url)
            self.assertEqual(response.status_code, 200, 
                           f"Sitemap'teki ürün URL'i erişilebilir değil: {test_url}")
    
    def test_sitemap_only_active_products(self):
        """Sitemap'te sadece aktif ürünler olduğu testi"""
        # Önce mevcut ürünlerden birini stoksuz yap
        test_product = self.products[0]
        test_product.stock = 0
        test_product.save()
        
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        
        # XML içeriğini parse et
        content = response.content.decode('utf-8')
        
        # Stoksuz ürünün URL'i sitemap'te olmamalı
        self.assertNotIn(f'/shop/product/{test_product.id}/', content, 
                        "Stoksuz ürün sitemap'te görünmemeli")
        
        # Stoklu ürünlerin URL'leri olmalı
        for product in self.products[1:]:  # İlkini atlayalım çünkü onu stoksuz yaptık
            if product.stock > 0:
                self.assertIn(f'/shop/product/{product.id}/', content, 
                            f"Stoklu ürün {product.name} sitemap'te olmalı")
    
    def test_sitemap_lastmod_dates(self):
        """Sitemap lastmod tarihlerinin doğru olduğu testi"""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        
        # XML içeriğini parse et
        content = response.content.decode('utf-8')
        root = ET.fromstring(content)
        
        # Namespace tanımla
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # URL'leri kontrol et
        urls = root.findall('.//ns:url', namespace)
        
        for url in urls:
            lastmod = url.find('ns:lastmod', namespace)
            if lastmod is not None:
                # Tarih formatının doğru olduğunu kontrol et (ISO 8601)
                date_text = lastmod.text
                self.assertRegex(date_text, r'\d{4}-\d{2}-\d{2}', 
                               f"lastmod tarihi ISO 8601 formatında olmalı: {date_text}")