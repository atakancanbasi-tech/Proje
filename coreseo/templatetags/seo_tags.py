from django import template
from django.utils.safestring import mark_safe
from django.contrib.contenttypes.models import ContentType
from ..models import SEOMetadata
import json

register = template.Library()

@register.simple_tag
def seo_meta_tags(obj=None, title=None, description=None, keywords=None):
    """Render SEO meta tags for an object or with custom values"""
    seo_data = None
    
    if obj:
        try:
            content_type = ContentType.objects.get_for_model(obj)
            seo_data = SEOMetadata.objects.get(content_type=content_type, object_id=obj.pk)
        except SEOMetadata.DoesNotExist:
            pass
    
    # Use custom values or fallback to SEO data
    meta_title = title or (seo_data.title if seo_data else '')
    meta_description = description or (seo_data.description if seo_data else '')
    meta_keywords = keywords or (seo_data.keywords if seo_data else '')
    
    html = []
    
    if meta_title:
        html.append(f'<title>{meta_title}</title>')
        html.append(f'<meta name="title" content="{meta_title}">')
    
    if meta_description:
        html.append(f'<meta name="description" content="{meta_description}">')
    
    if meta_keywords:
        html.append(f'<meta name="keywords" content="{meta_keywords}">')
    
    if seo_data:
        if seo_data.canonical_url:
            html.append(f'<link rel="canonical" href="{seo_data.canonical_url}">')
        
        if seo_data.noindex or seo_data.nofollow:
            robots = []
            if seo_data.noindex:
                robots.append('noindex')
            if seo_data.nofollow:
                robots.append('nofollow')
            html.append(f'<meta name="robots" content="{",".join(robots)}">')
    
    return mark_safe('\n'.join(html))

@register.simple_tag
def og_meta_tags(obj=None, title=None, description=None, image=None, url=None):
    """Render Open Graph meta tags"""
    seo_data = None
    
    if obj:
        try:
            content_type = ContentType.objects.get_for_model(obj)
            seo_data = SEOMetadata.objects.get(content_type=content_type, object_id=obj.pk)
        except SEOMetadata.DoesNotExist:
            pass
    
    og_title = title or (seo_data.og_title if seo_data else '')
    og_description = description or (seo_data.og_description if seo_data else '')
    og_image = image or (seo_data.og_image if seo_data else '')
    og_type = seo_data.og_type if seo_data else 'website'
    
    html = []
    
    if og_title:
        html.append(f'<meta property="og:title" content="{og_title}">')
    
    if og_description:
        html.append(f'<meta property="og:description" content="{og_description}">')
    
    if og_image:
        html.append(f'<meta property="og:image" content="{og_image}">')
    
    if url:
        html.append(f'<meta property="og:url" content="{url}">')
    
    html.append(f'<meta property="og:type" content="{og_type}">')
    
    return mark_safe('\n'.join(html))

@register.simple_tag
def twitter_meta_tags(obj=None, title=None, description=None, image=None):
    """Render Twitter Card meta tags"""
    seo_data = None
    
    if obj:
        try:
            content_type = ContentType.objects.get_for_model(obj)
            seo_data = SEOMetadata.objects.get(content_type=content_type, object_id=obj.pk)
        except SEOMetadata.DoesNotExist:
            pass
    
    twitter_card = seo_data.twitter_card if seo_data else 'summary_large_image'
    twitter_title = title or (seo_data.twitter_title if seo_data else '')
    twitter_description = description or (seo_data.twitter_description if seo_data else '')
    twitter_image = image or (seo_data.twitter_image if seo_data else '')
    
    html = []
    html.append(f'<meta name="twitter:card" content="{twitter_card}">')
    
    if twitter_title:
        html.append(f'<meta name="twitter:title" content="{twitter_title}">')
    
    if twitter_description:
        html.append(f'<meta name="twitter:description" content="{twitter_description}">')
    
    if twitter_image:
        html.append(f'<meta name="twitter:image" content="{twitter_image}">')
    
    return mark_safe('\n'.join(html))

@register.simple_tag
def schema_org_tags(obj=None, schema_type=None, schema_data=None):
    """Render Schema.org JSON-LD tags"""
    seo_data = None
    
    if obj:
        try:
            content_type = ContentType.objects.get_for_model(obj)
            seo_data = SEOMetadata.objects.get(content_type=content_type, object_id=obj.pk)
        except SEOMetadata.DoesNotExist:
            pass
    
    if not schema_type and seo_data:
        schema_type = seo_data.schema_type
    
    if not schema_data and seo_data:
        schema_data = seo_data.schema_data
    
    if not schema_type:
        return ''
    
    schema = {
        "@context": "https://schema.org",
        "@type": schema_type
    }
    
    if schema_data:
        schema.update(schema_data)
    
    return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')

@register.simple_tag
def all_seo_tags(obj=None, title=None, description=None, keywords=None, image=None, url=None):
    """Render all SEO tags at once"""
    html = []
    
    # Basic SEO
    html.append(seo_meta_tags(obj, title, description, keywords))
    
    # Open Graph
    html.append(og_meta_tags(obj, title, description, image, url))
    
    # Twitter Cards
    html.append(twitter_meta_tags(obj, title, description, image))
    
    # Schema.org
    html.append(schema_org_tags(obj))
    
    return mark_safe('\n'.join(filter(None, html)))