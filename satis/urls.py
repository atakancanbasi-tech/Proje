from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.contrib.auth import views as auth_views
from accounts.views import PasswordResetView as PasswordResetViewRL
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from payments import views as payments_views
from shop.sitemaps import ProductSitemap
from core import views as core_views
from accounts import views as account_views
from shop.views.order_actions import cancel_order

def redirect_to_products(request):
    return redirect('shop:product_list', permanent=True)

# Sitemap konfigürasyonu
sitemaps = {
    'products': ProductSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', redirect_to_products, name='home'),
    path('shop/', include('shop.urls', namespace='shop')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('security/', include('security.urls', namespace='security')),
    path('', include('coreseo.urls', namespace='coreseo')),
    # Payment callbacks
    path('payments/callback/iyzico/', payments_views.iyzico_callback, name='iyzico_callback'),
    path('payments/callback/paytr/', payments_views.paytr_callback, name='paytr_callback'),
    # Health check
    path('healthz/', core_views.healthz, name='healthz'),

    # Sipariş işlemleri
    path('orders/<int:order_id>/cancel/', cancel_order, name='order_cancel'),

    # E-posta doğrulama (kayıt onayı)
    path('accounts/verify/<uidb64>/<token>/', account_views.verify_email, name='verify_email'),
    path('accounts/resend-verification/', account_views.ResendVerificationView.as_view(), name='resend_verification'),

    # Hesap / Şifre Sıfırlama (Django auth CBV + Türkçe şablonlar + Rate Limiting)
    path('accounts/password-reset/', PasswordResetViewRL.as_view(), name='password_reset'),
    path(
        'accounts/password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'accounts/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'accounts/reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
    path('account/',  account_views.dashboard, name='account_dashboard'),
    # SEO
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots_txt'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
