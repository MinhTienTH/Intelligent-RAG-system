# Generated by Django 5.1.4 on 2024-12-06 13:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("qa_auto", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]