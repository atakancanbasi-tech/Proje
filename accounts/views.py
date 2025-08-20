from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib.auth.views import PasswordResetView as DjangoPasswordResetView
from django_ratelimit.decorators import ratelimit
from django.views import View
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.decorators import login_required


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('shop:product_list')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('shop:product_list')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('shop:product_list')


@method_decorator(ratelimit(key="ip", rate="5/m", block=True), name="dispatch")
class PasswordResetView(DjangoPasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")


# --- E-posta Doğrulama Yardımcıları ---
def _send_verification_email(request, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(
        reverse('verify_email', args=[uidb64, token])
    )
    ctx = {
        "user": user,
        "verify_link": link,
        "site_name": getattr(settings, "SITE_NAME", "Satış Sitesi"),
    }
    subject = render_to_string("registration/verify_email_subject.txt", ctx).strip()
    html = render_to_string("registration/verify_email_email.html", ctx)
    text = f"Merhaba {getattr(user, 'first_name', '')},\n\nHesabınızı doğrulamak için: {link}\n"
    send_mail(
        subject=subject or "E-posta doğrulama",
        message=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html,
        fail_silently=getattr(settings, 'EMAIL_FAIL_SILENTLY', True),
    )


class ResendVerificationView(View):
    """
    E-postayı tekrar gönder: dakikada 5 POST (IP bazlı).
    """
    def post(self, request):
        # Rate limiting kontrolü
        from django_ratelimit.core import is_ratelimited
        if is_ratelimited(request, group='resend_verification', key='ip', rate='5/m', increment=True):
            from django_ratelimit.exceptions import Ratelimited
            raise Ratelimited()
        email = request.POST.get("email", "").strip().lower()
        if not email:
            return HttpResponseBadRequest("E-posta gerekli.")
        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Bilgi sızdırmamak için her durumda 200 döneriz
            return render(request, "registration/verify_email_sent.html", status=200)
        # Zaten aktifse yine 200 (idempotent davranış)
        if getattr(user, "is_active", True):
            return render(request, "registration/verify_email_sent.html", status=200)
        _send_verification_email(request, user)
        return render(request, "registration/verify_email_sent.html", status=200)


def verify_email(request, uidb64, token):
    """
    Doğrulama linki: başarılıysa kullanıcıyı aktif eder ve başarı sayfasını gösterir.
    """
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        user = None
    
    ok = user and default_token_generator.check_token(user, token)
    if ok:
        if not getattr(user, "is_active", True):
            user.is_active = True
            user.save(update_fields=["is_active"])
        return render(request, "registration/verify_email_success.html", status=200)
    
    return render(request, "registration/verify_email_fail.html", status=400)


@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html", {})
