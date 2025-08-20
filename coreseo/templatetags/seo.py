import json
from django import template
from django.utils.html import format_html

register = template.Library()

@register.simple_tag
def jsonld(data: dict):
    return format_html(
        '<script type="application/ld+json">{}</script>',
        json.dumps(data, ensure_ascii=False)
    )

@register.simple_tag
def product_jsonld(product, site_url, brand="Vera Ovalis"):
    images = [site_url + img for img in getattr(product, "image_urls", [])][:6]
    offers = {
        "@type": "Offer",
        "priceCurrency": "TRY",
        "price": f"{getattr(product, 'price', 0):.2f}",
        "availability": "https://schema.org/InStock" if getattr(product, "in_stock", True) else "https://schema.org/OutOfStock",
        "url": site_url + getattr(product, "absolute_url", "/"),
    }
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": getattr(product, "name", ""),
        "image": images or [site_url + "/static/img/placeholder.webp"],
        "description": getattr(product, "short_desc", ""),
        "sku": getattr(product, "sku", ""),
        "brand": {"@type": "Brand", "name": brand},
        "offers": offers
    }
    return jsonld(data)

@register.simple_tag
def img_attrs(src, alt="", w=None, h=None, cls=""):
    parts = [f'src="{src}"', f'alt="{alt}"', 'loading="lazy"', 'decoding="async"']
    if w: parts.append(f'width="{w}"')
    if h: parts.append(f'height="{h}"')
    if cls: parts.append(f'class="{cls}"')
    return format_html("<img {}>", format_html(" ".join(parts)))