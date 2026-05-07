from django.contrib import admin

from .models import (
    Category,
    CompanyProfile,
    Enquiry,
    Project,
    ProjectField,
    ProjectFieldValue,
    ProjectImage,
)


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    fields = ('logo', 'favicon')

    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    list_editable = ('order',)
    ordering = ('order', 'name')
    prepopulated_fields = {'slug': ('name',)}

    def get_readonly_fields(self, request, obj=None):
        # Lock name/slug on edit; YAML owns them.
        return ('name', 'slug') if obj is not None else ()

    def get_prepopulated_fields(self, request, obj=None):
        # prepopulated_fields and readonly_fields conflict on edit.
        return {} if obj is not None else self.prepopulated_fields


@admin.register(ProjectField)
class ProjectFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'field_type', 'order')
    list_editable = ('order',)
    ordering = ('order', 'name')

    def get_readonly_fields(self, request, obj=None):
        return ('name', 'field_type') if obj is not None else ()


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    fields = ('image', 'caption', 'order')


class ProjectFieldValueInline(admin.TabularInline):
    model = ProjectFieldValue
    extra = 0
    fields = ('field', 'value')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'year_completed', 'is_featured', 'status')
    list_filter = ('category', 'is_featured', 'status')
    search_fields = ('title', 'location')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-year_completed', 'order')
    inlines = [ProjectImageInline, ProjectFieldValueInline]


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'project_type', 'created_at', 'is_read')
    list_filter = ('is_read', 'project_type')
    readonly_fields = ('name', 'email', 'project_type', 'message', 'created_at')
    actions = ['mark_as_read']

    def has_add_permission(self, request):
        return False

    @admin.action(description='Mark selected as read')
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(
            request,
            f'{updated} enquir{"y" if updated == 1 else "ies"} marked as read.',
        )
