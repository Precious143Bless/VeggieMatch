from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='VegetablePost',
            fields=[
                ('id',             models.BigAutoField(primary_key=True, serialize=False)),
                ('farmer_name',    models.CharField(max_length=100)),
                ('phone_number',   models.CharField(max_length=20)),
                ('farmer_photo',   models.ImageField(blank=True, null=True, upload_to='faces/farmers/')),
                ('vegetable',      models.CharField(max_length=100)),
                ('veggie_photo',   models.ImageField(blank=True, null=True, upload_to='veggies/')),
                ('surplus_level',  models.CharField(choices=[('LOW','Low Surplus (5-20 kg)'),('MEDIUM','Medium Surplus (20-100 kg)'),('HIGH','High Surplus (100+ kg)')], default='LOW', max_length=10)),
                ('quantity',       models.DecimalField(decimal_places=2, max_digits=8)),
                ('price_per_kg',   models.DecimalField(decimal_places=2, default=1.0, max_digits=8)),
                ('pickup_address', models.CharField(default='La Trinidad Trading Post, Benguet', max_length=255)),
                ('pickup_note',    models.CharField(blank=True, max_length=255)),
                ('status',         models.CharField(choices=[('ACTIVE','Active'),('BOUGHT','Bought'),('CLAIMED','Fully Claimed (Donated)'),('RESCUE','Available for Donate')], default='ACTIVE', max_length=10)),
                ('created_at',     models.DateTimeField(auto_now_add=True)),
                ('expiry_time',    models.DateTimeField()),
                ('expiry_notified', models.BooleanField(default=False)),
            ],
            options={'db_table': 'core_vegetablepost'},
        ),
        migrations.AddIndex(model_name='vegetablepost', index=models.Index(fields=['status'], name='idx_post_status')),
        migrations.AddIndex(model_name='vegetablepost', index=models.Index(fields=['expiry_time'], name='idx_post_expiry')),
        migrations.CreateModel(
            name='BuyRecord',
            fields=[
                ('id',           models.BigAutoField(primary_key=True, serialize=False)),
                ('post',         models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='buy', to='core.vegetablepost')),
                ('buyer_name',   models.CharField(max_length=100)),
                ('buyer_number', models.CharField(max_length=20)),
                ('buyer_photo',  models.ImageField(blank=True, null=True, upload_to='faces/buyers/')),
                ('quantity_kg',  models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('bought_at',    models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'core_buyrecord'},
        ),
        migrations.CreateModel(
            name='RescueRecord',
            fields=[
                ('id',             models.BigAutoField(primary_key=True, serialize=False)),
                ('post',           models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rescues', to='core.vegetablepost')),
                ('claimer_name',   models.CharField(max_length=100)),
                ('claimer_number', models.CharField(max_length=20)),
                ('claimer_photo',  models.ImageField(blank=True, null=True, upload_to='faces/claimers/')),
                ('quantity_kg',    models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('claimed_at',     models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'core_rescuerecord'},
        ),
        migrations.CreateModel(
            name='OTPVerification',
            fields=[
                ('id',           models.BigAutoField(primary_key=True, serialize=False)),
                ('phone_number', models.CharField(max_length=20)),
                ('otp_code',     models.CharField(max_length=6)),
                ('purpose',      models.CharField(choices=[('POST','Post'),('BUY','Buy'),('RESCUE','Rescue'),('DONATE','Donate'),('EDIT','Edit'),('DELETE','Delete'),('DASHBOARD','Dashboard')], max_length=10)),
                ('post_id',      models.BigIntegerField(blank=True, null=True)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('expires_at',   models.DateTimeField()),
                ('is_used',      models.BooleanField(default=False)),
            ],
            options={'db_table': 'core_otpverification'},
        ),
        migrations.AddIndex(model_name='otpverification', index=models.Index(fields=['phone_number', 'purpose'], name='idx_otp_phone_purpose')),
    ]
