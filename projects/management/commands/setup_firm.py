"""YAML → DB sync for categories, project fields, and projects.

Idempotent. YAML wins on overwrites for any project listed in it; admin edits to those
fields are clobbered and logged. Records present in the DB but missing from YAML are
left alone.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projects.models import (
    Category,
    Project,
    ProjectField,
    ProjectFieldValue,
    ProjectImage,
)


REQUIRED_KEYS = {'company', 'categories', 'services', 'project_fields', 'projects'}


class Command(BaseCommand):
    help = 'Sync categories, project fields, and projects from a YAML config file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--config',
            default='config.example.yaml',
            help='Path to the YAML config file (default: config.example.yaml).',
        )
        parser.add_argument(
            '--seed-images',
            default='seed_images',
            help='Directory containing source images referenced from the YAML (default: seed_images).',
        )

    def handle(self, *args, **options):
        config_path = Path(options['config']).resolve()
        seed_dir = Path(options['seed_images']).resolve()

        if not config_path.exists():
            raise CommandError(f'Config file not found: {config_path}')

        with config_path.open('r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise CommandError(f'Invalid YAML: {e}')

        missing = REQUIRED_KEYS - set(data.keys())
        if missing:
            raise CommandError(
                f'Missing top-level keys in config: {sorted(missing)}'
            )

        # One transaction for the whole sync — partial failures roll back.
        with transaction.atomic():
            n_cats = self._sync_categories(data.get('categories') or [])
            n_fields = self._sync_project_fields(data.get('project_fields') or [])
            n_projects = self._sync_projects(
                data.get('projects') or [], seed_dir
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSynced {n_cats} categories, {n_fields} project fields, '
                f'{n_projects} projects.'
            )
        )

    # -- categories -----------------------------------------------------

    def _sync_categories(self, categories):
        n = 0
        for entry in categories:
            slug = entry['slug']
            obj, created = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': entry['name'],
                    'order': entry.get('order', 0),
                },
            )
            verb = 'Created' if created else 'Updated'
            self.stdout.write(f'  Category: {verb} {obj.name} ({slug})')
            n += 1
        return n

    # -- project fields -------------------------------------------------

    def _sync_project_fields(self, fields):
        n = 0
        for entry in fields:
            obj, created = ProjectField.objects.update_or_create(
                name=entry['name'],
                defaults={
                    'field_type': entry.get('field_type', 'text'),
                    'order': entry.get('order', 0),
                },
            )
            verb = 'Created' if created else 'Updated'
            self.stdout.write(f'  ProjectField: {verb} {obj.name}')
            n += 1
        return n

    # -- projects -------------------------------------------------------

    def _sync_projects(self, projects, seed_dir):
        n = 0
        for entry in projects:
            slug = entry['slug']
            try:
                category = Category.objects.get(slug=entry['category'])
            except Category.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Project: SKIPPED "{slug}" — category '
                        f'"{entry["category"]}" not found'
                    )
                )
                continue

            payload = {
                'title': entry['title'],
                'category': category,
                'location': entry['location'],
                'year_completed': entry['year_completed'],
                'building_type': entry['building_type'],
                'area_sqft': entry.get('area_sqft'),
                'status': entry.get('status', 'built'),
                'description': entry['description'],
                'is_featured': entry.get('is_featured', False),
                'order': entry.get('order', 0),
            }

            existing = Project.objects.filter(slug=slug).first()
            if existing:
                # Drift between DB and YAML on YAML-controlled fields = admin edits about to be lost.
                overwritten = [
                    k for k, v in payload.items()
                    if getattr(existing, k) != v
                ]
                for k, v in payload.items():
                    setattr(existing, k, v)
                existing.save()
                project = existing
                if overwritten:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Project: Updated "{slug}" from YAML; '
                            f'overwrote admin edits on: {", ".join(overwritten)}'
                        )
                    )
                else:
                    self.stdout.write(f'  Project: Updated "{slug}" (no field changes)')
            else:
                project = Project.objects.create(slug=slug, **payload)
                self.stdout.write(f'  Project: Created "{slug}"')

            self._sync_featured_image(project, entry.get('featured_image'), seed_dir)
            self._sync_gallery(project, entry.get('gallery') or [], seed_dir)
            self._sync_field_values(project, entry.get('field_values') or [])
            n += 1
        return n

    # -- images ---------------------------------------------------------

    def _copy_seed(self, project, image_path, seed_dir):
        # Returns the relative path for ImageField, or None if source missing.
        src = seed_dir / image_path
        if not src.exists():
            self.stdout.write(
                self.style.WARNING(f'    Image not found, skipped: {src}')
            )
            return None
        dest_rel = f'projects/{project.category.slug}/{project.slug}/{src.name}'
        dest_abs = Path(settings.MEDIA_ROOT) / dest_rel
        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_abs)
        return dest_rel

    def _sync_featured_image(self, project, image_path, seed_dir):
        if not image_path:
            return
        dest_rel = self._copy_seed(project, image_path, seed_dir)
        if dest_rel and project.featured_image != dest_rel:
            project.featured_image = dest_rel
            project.save(update_fields=['featured_image'])

    def _sync_gallery(self, project, gallery, seed_dir):
        # Keyed on (project, order). Admin-added rows past the YAML's range survive re-runs.
        for idx, item in enumerate(gallery):
            dest_rel = self._copy_seed(project, item['image'], seed_dir)
            if not dest_rel:
                continue
            ProjectImage.objects.update_or_create(
                project=project,
                order=idx,
                defaults={
                    'image': dest_rel,
                    'caption': item.get('caption', ''),
                },
            )

    # -- field values ---------------------------------------------------

    def _sync_field_values(self, project, values):
        for entry in values:
            try:
                field = ProjectField.objects.get(name=entry['field'])
            except ProjectField.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f'    Field value SKIPPED: ProjectField '
                        f'"{entry["field"]}" not found'
                    )
                )
                continue
            ProjectFieldValue.objects.update_or_create(
                project=project,
                field=field,
                defaults={'value': entry['value']},
            )
