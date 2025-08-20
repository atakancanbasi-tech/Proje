from django.db import migrations, models
import django.core.validators

class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0015_orderstatushistory'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='billing_name',
        ),
        migrations.RemoveField(
            model_name='order',
            name='billing_tckn_vkn',
        ),
        migrations.RemoveField(
            model_name='order',
            name='billing_company_title',
        ),
        migrations.RemoveField(
            model_name='order',
            name='billing_tax_office',
        ),
        migrations.RemoveField(
            model_name='order',
            name='e_invoice',
        ),
        migrations.AddField(
            model_name='order',
            name='billing_fullname',
            field=models.CharField(blank=True, max_length=255, verbose_name='Fatura Ad Soyad/Ünvan'),
        ),
        migrations.AddField(
            model_name='order',
            name='tax_office',
            field=models.CharField(blank=True, max_length=128, verbose_name='Vergi Dairesi'),
        ),
        migrations.AddField(
            model_name='order',
            name='tckn',
            field=models.CharField(
                blank=True, max_length=11, verbose_name='TCKN',
                validators=[django.core.validators.RegexValidator('^\\d{11}$', 'TCKN 11 haneli rakam olmalıdır.')]
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='vkn',
            field=models.CharField(
                blank=True, max_length=10, verbose_name='VKN',
                validators=[django.core.validators.RegexValidator('^\\d{10}$', 'VKN 10 haneli rakam olmalıdır.')]
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='e_archive_email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='E-Arşiv E-posta'),
        ),
        migrations.AddField(
            model_name='order',
            name='billing_address',
            field=models.CharField(blank=True, max_length=500, verbose_name='Fatura Adresi'),
        ),
        migrations.AddField(
            model_name='order',
            name='billing_city',
            field=models.CharField(blank=True, max_length=64, verbose_name='İl'),
        ),
        migrations.AddField(
            model_name='order',
            name='billing_district',
            field=models.CharField(blank=True, max_length=64, verbose_name='İlçe'),
        ),
        migrations.AddField(
            model_name='order',
            name='billing_postcode',
            field=models.CharField(blank=True, max_length=10, verbose_name='Posta Kodu'),
        ),
        migrations.AddField(
            model_name='order',
            name='kvkk_approved',
            field=models.BooleanField(default=False, verbose_name='KVKK Aydınlatma Onayı'),
        ),
        migrations.AlterField(
            model_name='order',
            name='invoice_type',
            field=models.CharField(choices=[('bireysel','Bireysel'),('kurumsal','Kurumsal')], default='bireysel', max_length=10, verbose_name='Fatura Tipi'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['invoice_type'], name='shop_order_invoice_idx'),
        ),
    ]