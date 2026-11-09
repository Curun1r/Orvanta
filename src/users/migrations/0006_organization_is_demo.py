from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0005_user_hide_section_subtitles')]

    operations = [
        migrations.AddField(
            model_name='organization', name='is_demo',
            field=models.BooleanField(default=False),
        ),
    ]
