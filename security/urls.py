from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # Kimlik doğrulama URL'leri
    path('login/', views.secure_login, name='login'),
    path('logout/', views.secure_logout, name='logout'),
    path('register/', views.secure_register, name='register'),
    
    # İki faktörlü kimlik doğrulama
    path('2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
    path('2fa/resend/', views.resend_verification_code, name='resend_verification_code'),
    
    # Şifre yönetimi
    path('password/change/', views.change_password, name='change_password'),
    path('password/reset/', views.password_reset_request, name='password_reset_request'),
    path('password/reset/confirm/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    
    # Güvenlik ayarları
    path('settings/', views.security_settings, name='security_settings'),
    path('logs/', views.security_logs, name='security_logs'),
    
    # CAPTCHA URL'leri
    path('captcha/image/', views.generate_captcha_image, name='captcha_image'),
    path('captcha/refresh/', views.refresh_captcha, name='captcha_refresh'),
    path('captcha/cleanup/', views.cleanup_expired_captcha, name='captcha_cleanup'),
    
    # Şüpheli aktivite yönetimi
    path('dashboard/', views.security_dashboard, name='security_dashboard'),
    path('suspicious-activities/', views.suspicious_activities, name='suspicious_activities'),
    path('suspicious-activity/<int:activity_id>/', views.suspicious_activity_detail, name='suspicious_activity_detail'),
    path('suspicious-activity/<int:activity_id>/update/', views.update_suspicious_activity, name='update_suspicious_activity'),
    
    # Oturum ve Cihaz Yönetimi URL'leri
    path('sessions/', views.session_management, name='session_management'),
    path('sessions/<int:session_id>/end/', views.end_session, name='end_session'),
    path('sessions/end-all/', views.end_all_sessions, name='end_all_sessions'),
    path('sessions/<int:session_id>/', views.session_detail, name='session_detail'),
    path('devices/<int:device_id>/trust/', views.trust_device, name='trust_device'),
    path('devices/<int:device_id>/block/', views.block_device, name='block_device'),
    path('devices/<int:device_id>/rename/', views.rename_device, name='rename_device'),
    path('devices/<int:device_id>/', views.device_detail, name='device_detail'),
]