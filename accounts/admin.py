from django.contrib import admin
from .models import Address


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['title', 'fullname', 'city', 'district', 'user', 'is_default', 'created_at']
    list_filter = ['city', 'is_default', 'created_at']
    search_fields = ['title', 'fullname', 'city', 'district', 'address', 'user__username']
    list_editable = ['is_default']
    ordering = ['-created_at']
