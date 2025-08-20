from django import forms
import re
from .models import Order, ShippingCompany, PaymentMethod, Review
from decimal import Decimal


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'fullname', 'email', 'phone',
            'address', 'city', 'district', 'postal_code'
        ]
        widgets = {
            'fullname': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': True}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'district': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
        }
    
    def clean_fullname(self):
        val = self.cleaned_data['fullname'].strip()
        if not val:
            raise forms.ValidationError('Ad Soyad gerekli.')
        return val

    def clean_city(self):
        val = self.cleaned_data['city'].strip()
        if not val:
            raise forms.ValidationError('Şehir gerekli.')
        return val

    def clean_postal_code(self):
        val = self.cleaned_data['postal_code'].strip()
        if not val:
            raise forms.ValidationError('Posta kodu gerekli.')
        return val


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Yorumunuz için bir başlık (isteğe bağlı)'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Ürün hakkındaki deneyiminizi paylaşın...'
            })
        }
        labels = {
            'rating': 'Puanınız',
            'title': 'Başlık',
            'comment': 'Yorumunuz'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rating'].required = True


class BillingForm(forms.Form):
    want_invoice = forms.BooleanField(label='Fatura bilgisi girmek istiyorum', required=False)
    
    invoice_type = forms.ChoiceField(
        label='Fatura Tipi',
        choices=(('bireysel','Bireysel'),('kurumsal','Kurumsal')),
        initial='bireysel',
        required=False
    )
    
    billing_fullname = forms.CharField(label='Fatura Ad Soyad/Ünvan', max_length=255, required=False)
    tckn = forms.CharField(label='TCKN', max_length=11, required=False)
    vkn = forms.CharField(label='VKN', max_length=10, required=False)
    tax_office = forms.CharField(label='Vergi Dairesi', max_length=128, required=False)
    e_archive_email = forms.EmailField(label='E-Arşiv E-posta', required=False)
    billing_address = forms.CharField(label='Fatura Adresi', max_length=500, required=False, widget=forms.Textarea(attrs={'rows':2}))
    billing_city = forms.CharField(label='İl', max_length=64, required=False)
    billing_district = forms.CharField(label='İlçe', max_length=64, required=False)
    billing_postcode = forms.CharField(label='Posta Kodu', max_length=10, required=False)
    kvkk_approved = forms.BooleanField(label='KVKK Aydınlatma metnini okudum/onaylıyorum', required=False)
    
    def clean(self):
        data = super().clean()
        if not data.get('want_invoice'):
            return data  # tamamı opsiyonel
        
        itype = data.get('invoice_type') or 'bireysel'
        if itype == 'bireysel':
            if not data.get('tckn'):
                self.add_error('tckn', 'Bireysel fatura için TCKN zorunludur.')
            else:
                t = data.get('tckn', '')
                if not re.fullmatch(r'\d{11}', t):
                    self.add_error('tckn', 'TCKN 11 haneli rakam olmalıdır.')
        else:
            if not data.get('vkn'):
                self.add_error('vkn', 'Kurumsal fatura için VKN zorunludur.')
            if not data.get('billing_fullname'):
                self.add_error('billing_fullname', 'Kurumsal fatura için Ünvan zorunludur.')
            else:
                v = data.get('vkn', '')
                if not re.fullmatch(r'\d{10}', v):
                    self.add_error('vkn', 'VKN 10 haneli rakam olmalıdır.')
        
        return data