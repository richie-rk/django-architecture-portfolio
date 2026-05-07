from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path

import yaml
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from PIL import Image

from projects.forms import ContactForm
from projects.models import (
    Category,
    CompanyProfile,
    Enquiry,
    Project,
    ProjectField,
    ProjectFieldValue,
    ProjectImage,
    project_image_upload_path,
)


# Disable HTTPS redirect and axes for the test client; they're verified at the settings level.
TEST_OVERRIDES = dict(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@override_settings(**TEST_OVERRIDES)
class CategoryModelTests(TestCase):
    def test_create_and_retrieve(self):
        cat = Category.objects.create(name='Residential', slug='residential', order=1)
        self.assertEqual(str(cat), 'Residential')
        self.assertEqual(Category.objects.get(slug='residential'), cat)

    def test_default_ordering(self):
        Category.objects.create(name='B', slug='b', order=2)
        Category.objects.create(name='A', slug='a', order=1)
        names = list(Category.objects.values_list('name', flat=True))
        self.assertEqual(names, ['A', 'B'])


@override_settings(**TEST_OVERRIDES)
class ProjectFieldModelTests(TestCase):
    def test_create_and_retrieve(self):
        pf = ProjectField.objects.create(name='Awards', field_type='text', order=1)
        self.assertEqual(str(pf), 'Awards')
        self.assertEqual(pf.field_type, 'text')


@override_settings(**TEST_OVERRIDES)
class CompanyProfileSingletonTests(TestCase):
    def test_load_creates_or_returns_singleton(self):
        a = CompanyProfile.load()
        b = CompanyProfile.load()
        self.assertEqual(a.pk, 1)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(CompanyProfile.objects.count(), 1)

    def test_save_pins_pk_to_one(self):
        # A second CompanyProfile().save() must not create a second row.
        CompanyProfile.load()
        new = CompanyProfile()
        new.save()
        self.assertEqual(CompanyProfile.objects.count(), 1)
        self.assertEqual(new.pk, 1)

    def test_delete_is_a_noop(self):
        profile = CompanyProfile.load()
        profile.delete()
        self.assertEqual(CompanyProfile.objects.count(), 1)


@override_settings(**TEST_OVERRIDES)
class ProjectModelTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Residential', slug='residential', order=1)

    def test_slug_auto_generated_from_title(self):
        project = Project(
            title='Courtyard House',
            category=self.cat,
            location='Alibaug',
            year_completed=2023,
            building_type='Residence',
            description='...',
        )
        project.save()
        self.assertEqual(project.slug, 'courtyard-house')

    def test_explicit_slug_preserved(self):
        project = Project.objects.create(
            title='Anything', slug='custom-slug', category=self.cat,
            location='X', year_completed=2020, building_type='Y', description='z',
        )
        self.assertEqual(project.slug, 'custom-slug')

    def test_upload_path_routes_by_category_and_slug(self):
        project = Project.objects.create(
            title='Hill Retreat', category=self.cat,
            location='Lonavala', year_completed=2022, building_type='Residence',
            description='...',
        )
        path = project_image_upload_path(project, 'photo.jpg')
        self.assertEqual(path, 'projects/residential/hill-retreat/photo.jpg')

        img = ProjectImage(project=project)
        path2 = project_image_upload_path(img, 'gallery.jpg')
        self.assertEqual(path2, 'projects/residential/hill-retreat/gallery.jpg')

    def test_default_ordering_uses_year_completed_desc(self):
        Project.objects.create(
            title='A', category=self.cat, location='x', year_completed=2020,
            building_type='y', description='z',
        )
        Project.objects.create(
            title='B', category=self.cat, location='x', year_completed=2024,
            building_type='y', description='z',
        )
        titles = list(Project.objects.values_list('title', flat=True))
        self.assertEqual(titles, ['B', 'A'])


@override_settings(**TEST_OVERRIDES)
class ProjectFieldValueTests(TestCase):
    def test_unique_together_project_field(self):
        cat = Category.objects.create(name='R', slug='r')
        proj = Project.objects.create(
            title='P', category=cat, location='x', year_completed=2020,
            building_type='y', description='z',
        )
        field = ProjectField.objects.create(name='Awards', field_type='text', order=1)
        ProjectFieldValue.objects.create(project=proj, field=field, value='A')
        from django.db.utils import IntegrityError
        with self.assertRaises(IntegrityError):
            ProjectFieldValue.objects.create(project=proj, field=field, value='B')


@override_settings(**TEST_OVERRIDES)
class EnquiryModelTests(TestCase):
    def test_create_and_str(self):
        cat = Category.objects.create(name='Residential', slug='residential')
        e = Enquiry.objects.create(
            name='Asha Iyer', email='asha@example.com',
            project_type=cat, message='Hi.',
        )
        self.assertIn('Asha Iyer', str(e))
        self.assertIn('asha@example.com', str(e))


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

@override_settings(**TEST_OVERRIDES)
class URLResolutionTests(TestCase):
    def test_routes_resolve(self):
        cases = [
            ('/', 'projects:homepage'),
            ('/projects/', 'projects:list'),
            ('/projects/courtyard-house/', 'projects:detail'),
            ('/about/', 'projects:about'),
            ('/services/', 'projects:services'),
            ('/contact/', 'projects:contact'),
        ]
        for path, expected in cases:
            with self.subTest(path=path):
                match = resolve(path)
                self.assertEqual(f'{match.namespace}:{match.url_name}', expected)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@override_settings(**TEST_OVERRIDES)
class ViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cat_res = Category.objects.create(name='Residential', slug='residential', order=1)
        self.cat_com = Category.objects.create(name='Commercial', slug='commercial', order=2)
        self.featured = Project.objects.create(
            title='Featured One', category=self.cat_res, location='X',
            year_completed=2024, building_type='Y', description='hello',
            is_featured=True, order=1,
        )
        self.other = Project.objects.create(
            title='Other Project', category=self.cat_com, location='X',
            year_completed=2023, building_type='Y', description='hello',
            is_featured=False, order=2,
        )

    def test_homepage_200_and_template(self):
        r = self.client.get(reverse('projects:homepage'))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'projects/homepage.html')
        self.assertIn(self.featured, r.context['featured_projects'])
        self.assertNotIn(self.other, r.context['featured_projects'])

    def test_projects_list_no_filter(self):
        r = self.client.get(reverse('projects:list'))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'projects/projects_list.html')
        self.assertEqual(set(r.context['projects']), {self.featured, self.other})
        self.assertIsNone(r.context['selected_category'])

    def test_projects_list_category_filter(self):
        r = self.client.get(reverse('projects:list') + '?category=residential')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(r.context['projects']), [self.featured])
        self.assertEqual(r.context['selected_category'], self.cat_res)

    def test_projects_list_unknown_category_returns_all(self):
        r = self.client.get(reverse('projects:list') + '?category=nope')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context['selected_category'])
        self.assertEqual(set(r.context['projects']), {self.featured, self.other})

    def test_project_detail_200(self):
        r = self.client.get(reverse('projects:detail', args=[self.featured.slug]))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'projects/project_detail.html')
        self.assertEqual(r.context['project'], self.featured)

    def test_project_detail_unknown_slug_returns_404(self):
        r = self.client.get(reverse('projects:detail', args=['does-not-exist']))
        self.assertEqual(r.status_code, 404)

    def test_about_200(self):
        r = self.client.get(reverse('projects:about'))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'projects/about.html')

    def test_services_200(self):
        r = self.client.get(reverse('projects:services'))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'projects/services.html')

    def test_contact_get_renders_empty_form(self):
        r = self.client.get(reverse('projects:contact'))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'projects/contact.html')
        self.assertIsInstance(r.context['form'], ContactForm)

    def test_contact_post_creates_enquiry_and_redirects(self):
        r = self.client.post(reverse('projects:contact'), {
            'name': 'Asha Iyer',
            'email': 'asha@example.com',
            'project_type': self.cat_res.id,
            'message': 'I would like a Mumbai apartment.',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Enquiry.objects.count(), 1)
        e = Enquiry.objects.first()
        self.assertEqual(e.name, 'Asha Iyer')
        self.assertEqual(e.project_type, self.cat_res)


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------

@override_settings(**TEST_OVERRIDES)
class ContactFormTests(TestCase):
    def setUp(self):
        Category.objects.create(name='Residential', slug='residential', order=1)

    def _data(self, **overrides):
        base = {
            'name': 'Asha Iyer', 'email': 'asha@example.com',
            'message': 'A long-enough message goes here.',
        }
        base.update(overrides)
        return base

    def test_valid(self):
        self.assertTrue(ContactForm(self._data()).is_valid())

    def test_message_min_length(self):
        f = ContactForm(self._data(message='short'))
        self.assertFalse(f.is_valid())
        self.assertIn('message', f.errors)

    def test_email_format(self):
        f = ContactForm(self._data(email='not-an-email'))
        self.assertFalse(f.is_valid())
        self.assertIn('email', f.errors)

    def test_required_fields(self):
        f = ContactForm({'project_type': ''})
        self.assertFalse(f.is_valid())
        for field in ('name', 'email', 'message'):
            self.assertIn(field, f.errors)

    def test_project_type_optional(self):
        f = ContactForm(self._data())
        self.assertTrue(f.is_valid())
        e = f.save()
        self.assertIsNone(e.project_type)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@override_settings(**TEST_OVERRIDES)
class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw'
        )
        cls.cat = Category.objects.create(name='Residential', slug='residential', order=1)

    def setUp(self):
        self.client = Client()
        # force_login skips the auth backends, so axes doesn't see it.
        self.client.force_login(self.admin)

    def test_admin_index(self):
        r = self.client.get('/admin/')
        self.assertEqual(r.status_code, 200)

    def test_create_project_via_admin(self):
        r = self.client.post('/admin/projects/project/add/', {
            'title': 'New Build',
            'slug': 'new-build',
            'category': self.cat.id,
            'location': 'Pune',
            'year_completed': 2024,
            'building_type': 'House',
            'status': 'built',
            'description': 'Hello world',
            'order': 0,
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '1000',
            'field_values-TOTAL_FORMS': '0',
            'field_values-INITIAL_FORMS': '0',
            'field_values-MIN_NUM_FORMS': '0',
            'field_values-MAX_NUM_FORMS': '1000',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Project.objects.filter(slug='new-build').exists())

    def test_company_profile_singleton_blocks_second_add(self):
        from projects.admin import CompanyProfileAdmin
        from django.contrib import admin as django_admin
        site_admin = CompanyProfileAdmin(CompanyProfile, django_admin.site)
        request = RequestFactory().get('/admin/')
        request.user = self.admin

        self.assertTrue(site_admin.has_add_permission(request))
        CompanyProfile.load()
        self.assertFalse(site_admin.has_add_permission(request))

    def test_enquiry_admin_is_read_only(self):
        Enquiry.objects.create(name='A', email='a@b.c', message='hello world here.')
        r = self.client.get('/admin/projects/enquiry/add/')
        self.assertIn(r.status_code, (302, 403))


# ---------------------------------------------------------------------------
# setup_firm command
# ---------------------------------------------------------------------------

# Temp MEDIA_ROOT keeps seed-image copies out of the repo's media/.
TMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP_MEDIA, **TEST_OVERRIDES)
class SetupFirmCommandTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpdir = Path(tempfile.mkdtemp())
        cls.config_path = cls.tmpdir / 'config.yaml'
        cls.seed_dir = cls.tmpdir / 'seed_images'
        cls.seed_dir.mkdir()
        # Real JPEGs so ImageField validation passes if it ever fires.
        for rel in ('alpha-house/hero.jpg', 'alpha-house/01.jpg', 'beta-tower/hero.jpg'):
            target = cls.seed_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            img = Image.new('RGB', (32, 40), (200, 180, 140))
            img.save(target, 'JPEG', quality=70)

        cls.config_data = {
            'company': {
                'name': 'Test Firm', 'principal_architect': 'A. Test',
                'founding_year': 2000, 'biography': 'B', 'mission_statement': 'M',
                'credentials': ['X'], 'contact': {'email': 't@e.com'},
            },
            'categories': [
                {'name': 'Residential', 'slug': 'residential', 'order': 1},
                {'name': 'Commercial', 'slug': 'commercial', 'order': 2},
            ],
            'services': [
                {'name': 'Design', 'description': 'd', 'order': 1},
            ],
            'project_fields': [
                {'name': 'Awards', 'field_type': 'text', 'order': 1},
            ],
            'projects': [
                {
                    'title': 'Alpha House', 'slug': 'alpha-house',
                    'category': 'residential', 'location': 'A',
                    'year_completed': 2023, 'building_type': 'Home',
                    'area_sqft': 1500, 'status': 'built', 'description': 'd',
                    'is_featured': True, 'order': 1,
                    'featured_image': 'alpha-house/hero.jpg',
                    'gallery': [{'image': 'alpha-house/01.jpg', 'caption': 'c'}],
                    'field_values': [{'field': 'Awards', 'value': 'Gold'}],
                },
                {
                    'title': 'Beta Tower', 'slug': 'beta-tower',
                    'category': 'commercial', 'location': 'B',
                    'year_completed': 2024, 'building_type': 'Office',
                    'status': 'built', 'description': 'd',
                    'order': 2,
                    'featured_image': 'beta-tower/hero.jpg',
                },
            ],
        }
        with cls.config_path.open('w', encoding='utf-8') as f:
            yaml.safe_dump(cls.config_data, f)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def _run(self):
        out = io.StringIO()
        call_command(
            'setup_firm',
            config=str(self.config_path),
            seed_images=str(self.seed_dir),
            stdout=out,
        )
        return out.getvalue()

    def test_initial_run_seeds_db(self):
        self._run()
        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(ProjectField.objects.count(), 1)
        self.assertEqual(Project.objects.count(), 2)
        self.assertEqual(ProjectImage.objects.count(), 1)
        self.assertEqual(ProjectFieldValue.objects.count(), 1)

        alpha = Project.objects.get(slug='alpha-house')
        self.assertEqual(alpha.category.slug, 'residential')
        self.assertTrue(alpha.is_featured)
        self.assertEqual(alpha.featured_image.name, 'projects/residential/alpha-house/hero.jpg')

    def test_idempotent(self):
        self._run()
        first = (
            Category.objects.count(),
            ProjectField.objects.count(),
            Project.objects.count(),
            ProjectImage.objects.count(),
            ProjectFieldValue.objects.count(),
        )
        self._run()
        second = (
            Category.objects.count(),
            ProjectField.objects.count(),
            Project.objects.count(),
            ProjectImage.objects.count(),
            ProjectFieldValue.objects.count(),
        )
        self.assertEqual(first, second)

    def test_overwrites_admin_edits_and_logs_them(self):
        self._run()
        alpha = Project.objects.get(slug='alpha-house')
        alpha.description = 'admin edit'
        alpha.year_completed = 1900
        alpha.save()

        out = self._run()
        alpha.refresh_from_db()
        self.assertEqual(alpha.description, 'd')
        self.assertEqual(alpha.year_completed, 2023)
        self.assertIn('overwrote admin edits on', out)
        self.assertIn('description', out)
        self.assertIn('year_completed', out)

    def test_admin_added_project_not_in_yaml_is_preserved(self):
        self._run()
        cat = Category.objects.get(slug='residential')
        Project.objects.create(
            title='Admin Only', slug='admin-only', category=cat,
            location='X', year_completed=2020, building_type='Y', description='z',
        )
        self._run()
        self.assertTrue(Project.objects.filter(slug='admin-only').exists())

    def test_missing_config_raises(self):
        with self.assertRaises(CommandError):
            call_command('setup_firm', config='nonexistent.yaml',
                         seed_images=str(self.seed_dir))

    def test_missing_required_keys_raises(self):
        bad_path = self.tmpdir / 'bad.yaml'
        with bad_path.open('w', encoding='utf-8') as f:
            yaml.safe_dump({'company': {}}, f)
        with self.assertRaises(CommandError):
            call_command('setup_firm', config=str(bad_path),
                         seed_images=str(self.seed_dir))


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------

@override_settings(**TEST_OVERRIDES)
class ContactRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        Category.objects.create(name='Residential', slug='residential', order=1)

    def _post(self):
        return self.client.post(reverse('projects:contact'), {
            'name': 'A', 'email': 'a@b.c',
            'message': 'A long-enough message goes here.',
        })

    def test_sixth_post_is_blocked(self):
        for i in range(5):
            r = self._post()
            self.assertIn(r.status_code, (200, 302), f'submit {i} unexpectedly blocked')
        r = self._post()
        self.assertEqual(r.status_code, 403)
