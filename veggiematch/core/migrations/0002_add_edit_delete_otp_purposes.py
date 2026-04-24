from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='otpverification',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('POST', 'Post'), ('BUY', 'Buy'), ('RESCUE', 'Rescue'),
                    ('DONATE', 'Donate'), ('EDIT', 'Edit'), ('DELETE', 'Delete'),
                ],
                max_length=10,
            ),
        ),
    ]
