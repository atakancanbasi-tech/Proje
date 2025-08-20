from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class SEOMetadata(models.Model):
    """SEO metadata for any model"""
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    title = models.CharField(max_length=60, blank=True, help_text="SEO title (max 60 chars)")
    description = models.TextField(max_length=160, blank=True, help_text="Meta description (max 160 chars)")
    keywords = models.CharField(max_length=255, blank=True, help_text="Meta keywords")
    canonical_url = models.URLField(blank=True, help_text="Canonical URL")
    
    # Open Graph
    og_title = models.CharField(max_length=60, blank=True, help_text="Open Graph title")
    og_description = models.TextField(max_length=160, blank=True, help_text="Open Graph description")
    og_image = models.URLField(blank=True, help_text="Open Graph image URL")
    og_type = models.CharField(max_length=50, default='website', help_text="Open Graph type")
    
    # Twitter Card
    twitter_card = models.CharField(max_length=50, default='summary_large_image', help_text="Twitter card type")
    twitter_title = models.CharField(max_length=60, blank=True, help_text="Twitter title")
    twitter_description = models.TextField(max_length=160, blank=True, help_text="Twitter description")
    twitter_image = models.URLField(blank=True, help_text="Twitter image URL")
    
    # Schema.org
    schema_type = models.CharField(max_length=50, blank=True, help_text="Schema.org type")
    schema_data = models.JSONField(blank=True, null=True, help_text="Additional schema.org data")
    
    # SEO flags
    noindex = models.BooleanField(default=False, help_text="Prevent indexing")
    nofollow = models.BooleanField(default=False, help_text="Prevent following links")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('content_type', 'object_id')
        verbose_name = 'SEO Metadata'
        verbose_name_plural = 'SEO Metadata'
    
    def __str__(self):
        return f"SEO for {self.content_object}"

class SitemapEntry(models.Model):
    """Sitemap entries for better SEO"""
    url = models.URLField(unique=True)
    priority = models.DecimalField(max_digits=2, decimal_places=1, default=0.5, help_text="Priority (0.0-1.0)")
    changefreq = models.CharField(max_length=20, choices=[
        ('always', 'Always'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('never', 'Never'),
    ], default='weekly')
    lastmod = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Sitemap Entry'
        verbose_name_plural = 'Sitemap Entries'
        ordering = ['-priority', 'url']
    
    def __str__(self):
        return self.url