from django import template
from django.utils.html import format_html

register = template.Library()

@register.simple_tag
def img_default_attrs(w=300, h=200, decoding="async", loading="lazy"):
    """
    Kullanım:
    <img {% img_default_attrs 300 200 %} src="..." alt="...">
    -> width/height + decoding/loading özniteliklerini ekler.
    """
    return format_html('width="{}" height="{}" decoding="{}" loading="{}"', w, h, decoding, loading)