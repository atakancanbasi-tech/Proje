from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import EmailVerificationCode, SecurityLog, AccountLockout, UserSecuritySettings


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code_type', 'email', 'code', 'is_used', 'is_expired', 'created_at')
    list_filter = ('code_type', 'is_used', 'created_at')
    search_fields = ('user__username', 'user__email', 'email', 'code')
    readonly_fields = ('code', 'created_at', 'expires_at')
    ordering = ('-created_at',)
    
    def is_expired(self, obj):
        return obj.expires_at < timezone.now()
    is_expired.boolean = True
    is_expired.short_description = 'Süresi Dolmuş'
    
    def has_add_permission(self, request):
        return False  # Admin panelinden kod oluşturulmasın


@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'risk_level', 'ip_address', 'created_at')
    list_filter = ('event_type', 'risk_level', 'created_at')
    search_fields = ('user__username', 'user__email', 'ip_address', 'description')
    readonly_fields = ('user', 'event_type', 'risk_level', 'ip_address', 'user_agent', 'description', 'additional_data', 'created_at')
    ordering = ('-created_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        return False  # Admin panelinden log oluşturulmasın
    
    def has_change_permission(self, request, obj=None):
        return False  # Loglar değiştirilemez


@admin.register(AccountLockout)
class AccountLockoutAdmin(admin.ModelAdmin):
    list_display = ('user', 'reason', 'is_locked_status', 'locked_at', 'unlock_at', 'failed_attempts')
    list_filter = ('reason', 'is_permanent', 'locked_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('locked_at', 'failed_attempts', 'last_attempt_at')
    actions = ['unlock_accounts', 'lock_accounts_permanently']
    
    def is_locked_status(self, obj):
        if obj.is_locked():
            return format_html('<span style="color: red;">🔒 Kilitli</span>')
        else:
            return format_html('<span style="color: green;">🔓 Açık</span>')
    is_locked_status.short_description = 'Durum'
    
    def unlock_accounts(self, request, queryset):
        count = 0
        for lockout in queryset:
            if lockout.is_locked():
                lockout.unlock()
                count += 1
        
        self.message_user(request, f'{count} hesap kilidi açıldı.')
    unlock_accounts.short_description = 'Seçili hesapların kilidini aç'
    
    def lock_accounts_permanently(self, request, queryset):
        count = 0
        for lockout in queryset:
            lockout.is_permanent = True
            lockout.unlock_at = None
            lockout.save()
            count += 1
        
        self.message_user(request, f'{count} hesap kalıcı olarak kilitlendi.')
    lock_accounts_permanently.short_description = 'Seçili hesapları kalıcı kilitle'


@admin.register(UserSecuritySettings)
class UserSecuritySettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'two_factor_enabled', 'login_notifications', 'last_password_change', 'password_history_count')
    list_filter = ('two_factor_enabled', 'login_notifications', 'suspicious_activity_alerts')
    search_fields = ('user__username', 'user__email', 'backup_email')
    readonly_fields = ('created_at', 'updated_at', 'password_history_count')
    
    def password_history_count(self, obj):
        return len(obj.password_history or [])
    password_history_count.short_description = 'Şifre Geçmişi Sayısı'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# Admin site başlık ve başlık ayarları
admin.site.site_header = 'Satış Sitesi Güvenlik Yönetimi'
admin.site.site_title = 'Güvenlik Admin'
admin.site.index_title = 'Güvenlik Yönetim Paneli'