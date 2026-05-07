from django.db import models
from django.utils.text import slugify


def project_image_upload_path(instance, filename):
    # Same callable on Project.featured_image and ProjectImage.image; resolve through the parent.
    project = instance if isinstance(instance, Project) else instance.project
    return f'projects/{project.category.slug}/{project.slug}/{filename}'


class CompanyProfile(models.Model):
    # Singleton — admin-overridable logo/favicon only. Everything else is in config.yaml.

    logo = models.ImageField(upload_to='company/', blank=True, null=True)
    favicon = models.ImageField(upload_to='company/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company profile'
        verbose_name_plural = 'Company profile'

    def __str__(self):
        return 'Company profile'

    def save(self, *args, **kwargs):
        # Pin pk=1 always. Without the created_at preservation below, a second save() on
        # a fresh instance hits Django's UPDATE path and nulls created_at, since
        # auto_now_add only fires on INSERT.
        self.pk = 1
        existing = type(self).objects.filter(pk=1).first()
        if existing is not None:
            if not self.created_at:
                self.created_at = existing.created_at
            self._state.adding = False
        else:
            self._state.adding = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Singleton: refuse delete so the row is always there for admin to edit.
        return

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Category(models.Model):
    # YAML-managed. setup_firm syncs from config.yaml; admin can reorder, that's it.

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    order = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class ProjectField(models.Model):
    # YAML-managed. field_type is informational in v1 — values render as text, except
    # url-typed values which render as anchor tags in project_detail.html.

    FIELD_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('url', 'URL'),
    ]

    name = models.CharField(max_length=100, unique=True)
    field_type = models.CharField(max_length=10, choices=FIELD_TYPES, default='text')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Project(models.Model):
    STATUS_CHOICES = [
        ('built', 'Built'),
        ('under_construction', 'Under construction'),
        ('concept', 'Concept'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='projects')
    location = models.CharField(max_length=200)
    year_completed = models.IntegerField()
    building_type = models.CharField(max_length=200)
    area_sqft = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='built')
    description = models.TextField()
    featured_image = models.ImageField(
        upload_to=project_image_upload_path, blank=True, null=True
    )
    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-year_completed']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Admin's prepopulated_fields covers the UI; this catches ORM and shell creates.
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=project_image_upload_path)
    caption = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.project.title} — image {self.order}'


class ProjectFieldValue(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='field_values')
    field = models.ForeignKey(ProjectField, on_delete=models.CASCADE)
    value = models.TextField()

    class Meta:
        unique_together = [('project', 'field')]
        ordering = ['field__order']

    def __str__(self):
        return f'{self.project.title} — {self.field.name}'


class Enquiry(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    project_type = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Enquiries'

    def __str__(self):
        return f'{self.name} <{self.email}> — {self.created_at:%Y-%m-%d}'
