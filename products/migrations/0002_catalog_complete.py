# Phase 2: the catalog, complete — Tag, category slugs, product copy fields.
#
# Category.slug arrives in three steps (add nullable → backfill → tighten to
# unique non-null) so the migration applies cleanly to databases that already
# hold Phase 1 categories.

from django.db import migrations, models
from django.utils.text import slugify


def populate_category_slugs(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    for category in Category.objects.filter(slug__isnull=True):
        category.slug = slugify(category.name)
        category.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50, unique=True)),
                ("slug", models.SlugField(max_length=50, unique=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="category",
            name="slug",
            field=models.SlugField(max_length=100, null=True),
        ),
        migrations.RunPython(
            populate_category_slugs, migrations.RunPython.noop, elidable=True
        ),
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(max_length=100, unique=True),
        ),
        migrations.AddField(
            model_name="product",
            name="tagline",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="product",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="product",
            name="is_available",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="product",
            name="price",
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
        migrations.AddField(
            model_name="product",
            name="tags",
            field=models.ManyToManyField(
                blank=True, related_name="products", to="products.tag"
            ),
        ),
    ]
