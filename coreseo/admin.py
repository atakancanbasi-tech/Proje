from django.contrib import admin
from .models import SEOMetadata, SitemapEntry

@admin.register(SEOMetadata)
class SEOMetadataAdmin(admin.ModelAdmin):
    list_display = ('content_object', 'title', 'noindex', 'nofollow', 'updated_at')
    list_filter = ('content_type', 'noindex', 'nofollow', 'created_at')
    search_fields = ('title', 'description', 'keywords')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic SEO', {
            'fields': ('content_type', 'object_id', 'title', 'description', 'keywords', 'canonical_url')
        }),
        ('Open Graph', {
            'fields': ('og_title', 'og_description', 'og_image', 'og_type'),
            'classes': ('collapse',)
        }),
        ('Twitter Card', {
            'fields': ('twitter_card', 'twitter_title', 'twitter_description', 'twitter_image'),
            'classes': ('collapse',)
        }),
        ('Schema.org', {
            'fields': ('schema_type', 'schema_data'),
            'classes': ('collapse',)
        }),
        ('SEO Flags', {
            'fields': ('noindex', 'nofollow')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(SitemapEntry)
class SitemapEntryAdmin(admin.ModelAdmin):
    list_display = ('url', 'priority', 'changefreq', 'lastmod', 'is_active')
    list_filter = ('changefreq', 'is_active', 'priority')
    search_fields = ('url',)
    list_editable = ('priority', 'changefreq', 'is_active')
    readonly_fields = ('lastmod',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-priority', 'url')