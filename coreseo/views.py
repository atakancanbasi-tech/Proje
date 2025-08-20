from django.http import HttpResponse
from django.template import loader
from django.utils import timezone
from django.conf import settings
from .models import SitemapEntry

def sitemap_view(request):
    """Generate XML sitemap"""
    entries = SitemapEntry.objects.filter(is_active=True)
    
    template = loader.get_template('coreseo/sitemap.xml')
    context = {
        'entries': entries,
        'domain': getattr(settings, 'SITE_DOMAIN', 'localhost:8000'),
        'protocol': 'https' if getattr(settings, 'USE_HTTPS', False) else 'http',
    }
    
    xml_content = template.render(context, request)
    return HttpResponse(xml_content, content_type='application/xml')

def robots_view(request):
    """Generate robots.txt"""
    domain = getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
    protocol = 'https' if getattr(settings, 'USE_HTTPS', False) else 'http'
    
    robots_content = f"""User-agent: *
Allow: /

Sitemap: {protocol}://{domain}/sitemap.xml
"""
    
    return HttpResponse(robots_content, content_type='text/plain')