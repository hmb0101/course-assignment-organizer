from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assignments", "0002_assignment_unique_assignment_identity"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="submission_method",
            field=models.CharField(blank=True, max_length=255, verbose_name="提交方式"),
        ),
        migrations.AddField(
            model_name="assignment",
            name="content_requirements",
            field=models.TextField(blank=True, verbose_name="内容要求"),
        ),
        migrations.AddField(
            model_name="assignment",
            name="is_submitted",
            field=models.BooleanField(default=False, verbose_name="已提交"),
        ),
    ]
