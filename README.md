# Django Architecture Portfolio

<p align="center">
  <img src="docs/header.png" alt="Django Architecture Portfolio" width="100%">
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Django 5](https://img.shields.io/badge/Django-5.x-092e20.svg)](https://www.djangoproject.com/)
[![Tests](https://img.shields.io/badge/Tests-39%20passed-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/Coverage-96%25-brightgreen.svg)]()
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E.svg)](https://railway.app)

An open-source Django template for an architecture firm's portfolio website — server-side rendered, configured via a single YAML file at setup time, manageable via Django admin at runtime, and deployable to Railway in minutes.

<p align="center">
  <img src="docs/screenshots/01_homepage.png" alt="Homepage" width="800">
</p>

## Table of Contents
- [Overview](#overview)
- [Screenshots](#screenshots)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Acknowledgements](#acknowledgements)

## Overview

Django Architecture Portfolio is a complete, opinionated portfolio site for an architecture practice — built to be cloned, configured, and shipped without writing a line of Python. It pairs a single YAML file (firm name, biography, services, categories, project field schema, and seed projects) with a Django admin (live project records, gallery images, contact-form enquiries) so the same codebase can host any firm's portfolio.

The repo can be used as a **fork-and-deploy template** — clone, edit `config.yaml`, drop in photographs, push to Railway — or as a **starting point** for a bespoke build, with its models, admin customisations, middleware stack, security defaults, and CI/CD already wired up.

## Screenshots

### Homepage
Mission statement hero, stat block (projects completed, year established, practice areas), and a six-up grid of featured work.

<p align="center">
  <img src="docs/screenshots/01_homepage.png" alt="Homepage" width="800">
</p>

### Projects List
Filterable project grid with category tabs as GET params. Server-side filtered, no client-side JavaScript dependency.

<p align="center">
  <img src="docs/screenshots/02_projects_list.png" alt="Projects List" width="800">
</p>

### Project Detail
Full-bleed hero, structured metadata sidebar (type, area, status, plus YAML-defined custom fields like Awards or Sustainability Rating), and a gallery grid.

<p align="center">
  <img src="docs/screenshots/03_project_detail.png" alt="Project Detail" width="800">
</p>

### About & Services
Mission statement, biography, credentials, and the services list — all driven by `config.yaml`, never the database.

<p align="center">
  <img src="docs/screenshots/04_about_services.png" alt="About and Services" width="800">
</p>

### Contact
Rate-limited (5/h per IP) contact form with project-type filter. Valid POSTs save an Enquiry and email the admin.

<p align="center">
  <img src="docs/screenshots/05_contact.png" alt="Contact form" width="800">
</p>

### Django Admin
Full CRUD over projects, gallery images, custom field values, and enquiries. Logo and favicon overrides on the singleton CompanyProfile. Brute-force protected by django-axes.

<p align="center">
  <img src="docs/screenshots/06_admin.png" alt="Django Admin" width="800">
</p>

## Features

- **YAML-Driven Setup**: A single `config.yaml` defines the firm — company info, services, categories, custom project field schema, and seed projects. The `setup_firm` management command idempotently syncs YAML to the database.
- **Static / Dynamic Split**: Setup-time constants live in YAML and reach templates via a context processor; runtime content (projects, images, enquiries) lives in the database and is editable via Django admin. Mixing the two is a deliberate non-goal.
- **Six Public Pages**: Homepage, Projects list (with category filter), Project detail (with prefetched gallery and custom fields), About, Services, Contact — all server-side rendered with Tailwind via CDN.
- **Custom Project Fields**: Define arbitrary metadata fields (`Client Type`, `Awards`, `Sustainability Rating`, `Photography`, etc.) per firm in YAML; admins fill values per project.
- **Routed Image Uploads**: Featured images and gallery images route to `media/projects/<category-slug>/<project-slug>/<filename>` via a callable `upload_to`, so storage layout mirrors URL structure.
- **Singleton CompanyProfile**: Admin-uploadable logo and favicon override the repo's default SVGs at render time, enforced as single-row at both the admin and ORM levels.
- **Idempotent YAML Sync with Overwrite Logging**: Re-running `setup_firm` upserts every YAML-listed project by slug and prints a per-project diff of fields it just clobbered, so YAML stays the source of truth without silently overwriting admin edits.
- **Brute-Force Protection**: `/admin/` is gated by django-axes — 5 failed attempts per IP triggers a 30-minute lockout.
- **Rate Limiting**: The contact view is throttled to 5 submissions per hour per IP via django-ratelimit.
- **HTTPS Everywhere in Production**: SSL redirect, secure session and CSRF cookies, HSTS, and X-Frame-Options auto-enable when `DEBUG=False`.
- **Railway-Ready**: Procfile, `railway.toml`, and a GitHub Actions workflow that gates Railway deploys on a green test suite.
- **39 Tests, 96% Coverage**: Models, views, forms, admin, URL resolution, the YAML sync command (including idempotency and overwrite-logging), and the contact-form rate limit are all under test.

## Architecture

The system is a single Django app with strict separation between configuration (YAML, set at process start), runtime data (database, edited via admin), and visual assets (repo files):

```
Browser  <-->  Django Templates (projects/templates/)  <-->  Django App (projects/)
                                                                       |
                                            +--------------------------+--------------------------+
                                            |                          |                          |
                                            v                          v                          v
                                       YAML Config             Postgres / SQLite             Static Assets
                                      (config.yaml)              project DB              (default-logo.svg,
                                   loaded at startup           edited via admin           default-favicon.svg)
```

### **Static Configuration (`config.yaml` → Django settings/context)**
- **Loaded once at startup**: Read by `config/settings.py` into `settings.FIRM_CONFIG`, exposed to all templates via the `firm_config` context processor as `{{ firm.* }}`.
- **What lives here**: Company name, principal architect, founding year, biography, mission statement, credentials, contact details, services list, categories list, custom project field definitions.
- **Why YAML, not the database**: These rarely change for a given firm — admin can't accidentally rename the company, and there's no per-request DB query for static text.

### **Dynamic Data (Database → Django admin)**
- **Stored in Postgres / SQLite**: Project records, ProjectImage galleries, ProjectFieldValues, Enquiries, plus the singleton CompanyProfile (logo/favicon overrides).
- **Edited via `/admin/`**: Standard Django admin with `prepopulated_fields` for slugs, `TabularInline` for gallery and custom field values, and a read-only Enquiry viewer with a "mark as read" action.

### **Hybrid: Categories & ProjectFields**
- **Defined in YAML, synced to DB**: So `Project.category` can foreign-key against them. Admin can edit display order; name and slug are locked on the change form via `get_readonly_fields(obj=...)`.

### **Static Assets (`projects/static/projects/img/`)**
- **Repo-tracked SVGs**: `default-logo.svg` and `default-favicon.svg` ship with the template.
- **Override hierarchy at render time**: `CompanyProfile.logo` (admin upload, stored under `media/`) → repo default. Same for favicon.

### **Security Stack**
- **HTTPS-only in production**: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS, and `X_FRAME_OPTIONS=DENY` all activate when `DEBUG=False`.
- **Brute-force protection**: `axes.AxesStandaloneBackend` first in `AUTHENTICATION_BACKENDS`; 5 fails → 30-min IP lockout.
- **Rate limiting**: `@ratelimit(key='ip', rate='5/h', block=True)` on the contact view.
- **CSRF + WhiteNoise**: Standard CSRF middleware, plus WhiteNoise's `CompressedManifestStaticFilesStorage` for hashed static asset serving.

## Installation

### Prerequisites
- Python 3.12+ (CI tests against 3.12; local dev verified on 3.13)
- pip (or uv / pipx)
- PostgreSQL for production; SQLite is the local default
- Optional: a Railway account with a Postgres plugin for deployment

### Setup

1. **Clone the repository**:
   ```bash
   git clone <your-fork-url>
   cd django-architecture-portfolio
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate         # On Windows: .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment and firm**:
   ```bash
   cp .env.example .env
   cp config.example.yaml config.yaml
   ```

   `.env` controls the runtime (`DEBUG`, `SECRET_KEY`, `DATABASE_URL`, SMTP). `config.yaml` defines the firm. Both are gitignored — only commit them to a private fork.

5. **Generate placeholder seed images** (skip if you've dropped your own JPEGs into `seed_images/`):
   ```bash
   python tools/generate_seed_images.py
   ```

6. **Migrate the database and seed the demo content**:
   ```bash
   python manage.py migrate
   python manage.py setup_firm --config config.yaml
   ```

7. **Create an admin user and start the dev server**:
   ```bash
   python manage.py createsuperuser
   python manage.py runserver
   ```

   Public site at <http://127.0.0.1:8000/>; admin at <http://127.0.0.1:8000/admin/>.

## Usage

### **Quick Start — Local Dev Server**

```bash
python manage.py runserver
```

With the demo `config.example.yaml` seeded, you'll see twelve sample projects across Residential, Commercial, Institutional, Urban Design, and Interiors categories; four services on the Services page; and a Contact form whose project-type dropdown is populated from your YAML categories.

### **Editing Firm Data**

Two distinct edit paths, depending on what's changing:

| Change                                                  | Where to edit                              | Reload required?       |
|---------------------------------------------------------|--------------------------------------------|------------------------|
| Company name, biography, services, categories, fields   | `config.yaml` + `setup_firm`               | Yes (process restart)  |
| Project records, gallery images, custom field values    | Django admin (`/admin/`)                   | No                     |
| Logo, favicon                                           | Admin → CompanyProfile                     | No                     |
| Default logo/favicon SVGs                               | `projects/static/projects/img/`            | Yes (`collectstatic`)  |
| Tailwind palette, typography                            | `projects/templates/projects/base.html`    | Browser refresh        |

### **Re-running `setup_firm`**

The command is idempotent. Re-running with the same YAML produces the same DB state. Re-running after editing YAML upserts every listed project by slug and **logs every field where it overwrote an admin edit**:

```text
  Project: Updated "courtyard-house" from YAML; overwrote admin edits on: description, year_completed
```

YAML wins for any project listed there — projects are configuration, admins should treat them as such. Projects added through admin that aren't in YAML are never touched.

### **Library Mode — Reuse the Models**

The `projects` app is importable without the YAML or the runserver. Useful when wiring the data layer into a different frontend or a one-off script:

```python
from projects.models import Category, Project

residential = Category.objects.get(slug='residential')
featured = (
    Project.objects.filter(is_featured=True)
    .select_related('category')
    .order_by('order', '-year_completed')
)

for project in featured:
    print(f'{project.title} — {project.category.name} — {project.year_completed}')
```

### **Generating Seed Images from a Custom YAML**

```bash
python tools/generate_seed_images.py
```

Reads `config.example.yaml`, walks every `featured_image` and `gallery[*].image` reference, and produces a 1200x1500 placeholder JPEG at the corresponding path under `seed_images/`. Replace with real photographs before deploying publicly.

## Configuration

### **YAML Schema (`config.yaml`)**

```yaml
company:
  name: "Studio Modern Architecture"
  principal_architect: "Ar. Anjali Mehra"
  founding_year: 2010
  total_projects_completed: 250
  biography: |
    Multi-line biography...
  mission_statement: |
    One- or two-line mission statement...
  credentials:
    - "Council of Architecture, India"
    - "LEED Accredited Professional"
  contact:
    email: "hello@example.com"
    phone: "+91 22 1234 5678"
    address: |
      Multi-line postal address

categories:
  - { name: "Residential",   slug: "residential",   order: 1 }
  - { name: "Commercial",    slug: "commercial",    order: 2 }

services:
  - { name: "Architectural Design", description: "...", order: 1 }

project_fields:
  - { name: "Client Type",    field_type: "text", order: 1 }
  - { name: "Awards",         field_type: "text", order: 2 }

projects:
  - title: "Courtyard House"
    slug: "courtyard-house"
    category: "residential"
    location: "Alibaug, Maharashtra"
    year_completed: 2023
    building_type: "Single-family residence"
    area_sqft: 4200
    status: "built"             # built | under_construction | concept
    description: |
      Multi-line description...
    featured_image: "courtyard-house/hero.jpg"
    is_featured: true
    order: 1
    gallery:
      - { image: "courtyard-house/01.jpg", caption: "Approach view" }
    field_values:
      - { field: "Client Type", value: "Private" }
```

### **Environment Variables (`.env`)**

| Variable                                           | Default                                            | Notes                                                          |
|----------------------------------------------------|----------------------------------------------------|----------------------------------------------------------------|
| `SECRET_KEY`                                       | `dev-insecure-change-me-before-deploy`             | Required in production. Generate a long random string.         |
| `DEBUG`                                            | `False`                                            | Set `True` for local dev so HTTPS redirect doesn't kick in.    |
| `ALLOWED_HOSTS`                                    | `*`                                                | Comma-separated. Tighten in production.                        |
| `DATABASE_URL`                                     | SQLite at `db.sqlite3`                             | `dj-database-url`-compatible. Postgres on Railway.             |
| `FIRM_CONFIG_PATH`                                 | `<repo>/config.yaml`                               | Path to the YAML loaded at process start.                      |
| `ADMIN_EMAIL`                                      | `admin@example.com`                                | Recipient of contact-form Enquiry notifications.               |
| `EMAIL_BACKEND`                                    | `django.core.mail.backends.console.EmailBackend`   | Console for dev; SMTP backend for production.                  |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_USE_TLS` | —                       | SMTP credentials when `EMAIL_BACKEND` is the SMTP backend.     |

### **`setup_firm` Flags**

| Flag             | Default               | Description                                                          |
|------------------|-----------------------|----------------------------------------------------------------------|
| `--config`       | `config.example.yaml` | Path to the YAML config to sync.                                     |
| `--seed-images`  | `seed_images`         | Directory containing source images referenced from the YAML.         |

### **Visual System**

| Token         | Value      | Used for                                  |
|---------------|------------|-------------------------------------------|
| `bg`          | `#FAFAF7`  | Page background (warm off-white)          |
| `ink`         | `#1A1A1A`  | Primary text                              |
| `muted`       | `#6B6B6B`  | Secondary text, captions, metadata labels |
| `accent`      | `#8B6F47`  | Hover states, accents, error numbers      |
| `border`      | `#E8E6E1`  | Hairline borders, image placeholders      |
| Serif font    | Fraunces   | Headings, large display numbers           |
| Sans font     | Inter      | Body, navigation, UI                      |

Edit the `tailwind.config` block in `projects/templates/projects/base.html` to change any of the above.

## Testing

```bash
# Full suite
python manage.py test

# With coverage
coverage run --source=projects manage.py test
coverage report --skip-covered
```

### **Test Coverage**

| Class                              | Tests | Key validations                                                                                                |
|------------------------------------|-------|----------------------------------------------------------------------------------------------------------------|
| `CategoryModelTests`               | 2     | Create/retrieve, default ordering by `order` then `name`                                                       |
| `ProjectFieldModelTests`           | 1     | Create/retrieve with field_type                                                                                |
| `CompanyProfileSingletonTests`     | 3     | `load()` idempotent, `save()` pins pk=1, `delete()` is a no-op                                                 |
| `ProjectModelTests`                | 4     | Slug auto-generated from title, explicit slug preserved, upload path routes by category, ordering by year desc |
| `ProjectFieldValueTests`           | 1     | `unique_together(project, field)` enforced                                                                     |
| `EnquiryModelTests`                | 1     | Create + str representation                                                                                    |
| `URLResolutionTests`               | 1     | All six routes resolve to the right `namespace:name`                                                           |
| `ViewTests`                        | 10    | Status codes, templates, context, category filter, 404 on unknown slug, contact POST                           |
| `ContactFormTests`                 | 5     | Validation rules, message min length, email format, required fields, optional project_type                     |
| `AdminTests`                       | 4     | Admin index, project create, singleton add-block, enquiry read-only                                            |
| `SetupFirmCommandTests`            | 6     | Initial seed, idempotency, admin-edit overwrite logging, admin-added preservation, missing config, missing keys|
| `ContactRateLimitTests`            | 1     | 6th submission within 5/h window blocked (403 from django-ratelimit)                                           |

Coverage targets ≥80% on `projects/`, enforced in CI via `coverage report --fail-under=80`. Current coverage is 96% on the full app, with every covered file at 80% or above.

## Project Structure

```
django-architecture-portfolio/
├── manage.py                            # Django CLI entry
├── requirements.txt                     # Pinned runtime dependencies
├── README.md                            # This file
├── CLAUDE.md                            # Build conventions for Claude Code
├── IMPLEMENTATION_SPEC.md               # v1 technical specification
├── config.example.yaml                  # Sample firm config — 12 projects, 5 categories
├── .env.example                         # Environment-variable template
├── Procfile                             # Railway / Heroku process declaration
├── railway.toml                         # Railway build/deploy config
├── .gitignore
│
├── config/                              # Django project root
│   ├── settings.py                      # YAML loader, middleware, axes config, HTTPS-on-prod
│   ├── urls.py                          # Root URL conf, error handlers, dev media serving
│   ├── wsgi.py                          # Gunicorn entry point
│   └── asgi.py
│
├── projects/                            # Single Django app
│   ├── models.py                        # 7 models: CompanyProfile, Category, ProjectField,
│   │                                    #          Project, ProjectImage, ProjectFieldValue, Enquiry
│   ├── admin.py                         # Singleton check, readonly enforcement, inlines, mark-as-read
│   ├── views.py                         # 6 public views + handler404 + handler500
│   ├── urls.py                          # `projects:` namespaced routes
│   ├── forms.py                         # Tailwind-styled ContactForm with rebound queryset
│   ├── context_processors.py            # Injects firm + company_profile into all templates
│   ├── apps.py
│   ├── tests.py                         # 39 tests, 96% coverage
│   ├── migrations/
│   │   └── 0001_initial.py
│   ├── management/
│   │   └── commands/
│   │       └── setup_firm.py            # Idempotent YAML → DB sync with overwrite logging
│   ├── templates/projects/
│   │   ├── base.html                    # Tailwind via CDN, Fraunces + Inter, palette tokens
│   │   ├── homepage.html
│   │   ├── projects_list.html
│   │   ├── project_detail.html
│   │   ├── about.html
│   │   ├── services.html
│   │   ├── contact.html
│   │   ├── 404.html
│   │   └── 500.html
│   └── static/projects/
│       └── img/
│           ├── default-logo.svg
│           └── default-favicon.svg
│
├── seed_images/                         # Source images referenced from YAML
│   └── <project-slug>/<filename>.jpg    # Copied to media/ by setup_firm
│
├── tools/
│   └── generate_seed_images.py          # Generates placeholder JPEGs from YAML
│
└── .github/
    └── workflows/
        └── deploy.yml                   # Test on every push; Railway deploy on green main
```

## Deployment

The repo ships with a `Procfile`, `railway.toml`, and a GitHub Actions workflow that gates Railway deploys on tests passing.

### **Railway**

1. **Push to GitHub** and connect the repo at <https://railway.app>.
2. **Add a Postgres plugin** to the Railway project. `DATABASE_URL` is injected automatically.
3. **Set environment variables** in the Railway dashboard (mirror `.env.example`):

   | Variable             | Value                                              |
   |----------------------|----------------------------------------------------|
   | `SECRET_KEY`         | Long random string                                 |
   | `DEBUG`              | `False`                                            |
   | `ALLOWED_HOSTS`      | `*.up.railway.app,yourcustomdomain.com`            |
   | `FIRM_CONFIG_PATH`   | `/app/config.yaml`                                 |
   | `ADMIN_EMAIL`        | Where contact-form notifications go                |
   | `EMAIL_BACKEND`      | `django.core.mail.backends.smtp.EmailBackend`      |
   | `EMAIL_HOST` etc.    | SMTP credentials                                   |

4. **Add GitHub Actions secrets** under repo → Settings → Secrets and variables → Actions:
   - `RAILWAY_TOKEN` — generated at Railway → Account Settings → Tokens
   - `RAILWAY_SERVICE` — your Railway service name

5. **Set the Railway spending cap. This is non-optional.**

   > Railway dashboard → Account Settings → Billing → **Spend Limit: $5.10/month**

   Ten cents above the free-tier ceiling — enough headroom for a brief traffic spike, low enough that a runaway loop or accidentally-public admin endpoint cannot generate a four-figure bill. Re-check this any time the project's billing arrangement changes.

6. **Push to `main`**. GitHub Actions runs the test suite; on green, `railway up` deploys to your service. The `release` step in the Procfile migrates the DB before gunicorn starts.

7. **Create a superuser on the deployed instance**:
   ```bash
   railway run python manage.py createsuperuser
   ```

### **Custom Domain**

Configure under Railway → Service → Settings → Networking. Point a CNAME at the auto-generated `*.up.railway.app` host, then add the custom domain to `ALLOWED_HOSTS` in the Railway env vars.

## Acknowledgements

- Built with [Django](https://www.djangoproject.com/), [Tailwind CSS](https://tailwindcss.com/), [Pillow](https://python-pillow.org/), [WhiteNoise](https://whitenoise.evans.io/), [django-axes](https://django-axes.readthedocs.io/), [django-ratelimit](https://django-ratelimit.readthedocs.io/), [python-decouple](https://github.com/HBNetwork/python-decouple), [dj-database-url](https://github.com/jazzband/dj-database-url), [PyYAML](https://pyyaml.org/), and [Gunicorn](https://gunicorn.org/)
- Typography by [Fraunces](https://fonts.google.com/specimen/Fraunces) and [Inter](https://rsms.me/inter/), via Google Fonts
- Hosted on [Railway](https://railway.app), with CI on [GitHub Actions](https://github.com/features/actions)
- Build conventions and the YAML / dynamic-data split inspired by years of architecture studios fighting their CMS — this template aims to give them less to fight

---

Built for architecture practices and the Django community
