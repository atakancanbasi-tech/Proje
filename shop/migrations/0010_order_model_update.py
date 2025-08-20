# Generated manually
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0009_productattribute_productattributevalue_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Order modelini güncelle
        migrations.RemoveField(
            model_name='order',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='order',
            name='last_name',
        ),
        migrations.RemoveField(
            model_name='order',
            name='subtotal',
        ),
        migrations.RemoveField(
            model_name='order',
            name='shipping_cost',
        ),
        migrations.RemoveField(
            model_name='order',
            name='processing_fee',
        ),
        migrations.RemoveField(
            model_name='order',
            name='discount_amount',
        ),
        migrations.RemoveField(
            model_name='order',
            name='total_amount',
        ),
        migrations.RemoveField(
            model_name='order',
            name='shipping_company',
        ),
        migrations.RemoveField(
            model_name='order',
            name='tracking_number',
        ),
        migrations.RemoveField(
            model_name='order',
            name='estimated_delivery_date',
        ),
        migrations.RemoveField(
            model_name='order',
            name='payment_method',
        ),
        migrations.RemoveField(
            model_name='order',
            name='payment_status',
        ),
        migrations.RemoveField(
            model_name='order',
            name='payment_date',
        ),
        migrations.RemoveField(
            model_name='order',
            name='payment_reference',
        ),
        migrations.RemoveField(
            model_name='order',
            name='updated_at',
        ),
        migrations.RemoveField(
            model_name='order',
            name='coupon',
        ),
        
        # Yeni alanları ekle
        migrations.AddField(
            model_name='order',
            name='fullname',
            field=models.CharField(max_length=120, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='district',
            field=models.CharField(max_length=60, blank=True),
        ),
        migrations.AddField(
            model_name='order',
            name='total',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0),
            preserve_default=False,
        ),
        
        # Status alanını güncelle
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('received', 'Alındı'),
                    ('paid', 'Ödendi'),
                    ('shipped', 'Kargolandı'),
                    ('cancelled', 'İptal')
                ],
                default='received',
                max_length=16
            ),
        ),
        
        # OrderItem modelini güncelle
        migrations.RemoveField(
            model_name='orderitem',
            name='price',
        ),
        migrations.AddField(
            model_name='orderitem',
            name='unit_price',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='orderitem',
            name='line_total',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0),
            preserve_default=False,
        ),
        
        # Product modeline on_delete=PROTECT ekle
        migrations.AlterField(
            model_name='orderitem',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='shop.product'),
        ),
    ]