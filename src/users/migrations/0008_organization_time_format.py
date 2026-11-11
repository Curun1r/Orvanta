from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0007_alter_organization_options_alter_user_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='time_format',
            field=models.CharField(
                choices=[('24', '24-hour (14:30)'), ('12', '12-hour (2:30 PM)')],
                default='24',
                max_length=2,
                verbose_name='Time format',
            ),
        ),
    ]
