# Orvanta

[![CI](https://github.com/Curun1r/Orvanta/actions/workflows/ci.yml/badge.svg)](https://github.com/Curun1r/Orvanta/actions/workflows/ci.yml)

A Django application for service businesses: appointments, clients, staff, and financial analytics in separate organization workspaces. Built as a bachelor's thesis project, with particular attention to access control, consistent booking, and traceable changes.

> **Stack:** Python · Django · PostgreSQL · Bootstrap 5 · Chart.js · Django REST Framework · Railway

[Run the local demo](#local-demo-docker) · [Read the backend case study](docs/portfolio-case-study.md) · [Explore the tests](#tests)

The demo uses generated data and accounts for Admin, Manager, and Employee. It can be reproduced locally with Docker.

---

## Overview

Orvanta is built as a multi-tenant web application. Each registered business creates its own organization workspace, and all business data is isolated within that organization.

The system supports:

- organization-based data isolation
- user authentication with organization-scoped login
- role-based access control (Admin, Manager, Employee)
- client management
- service catalog and category management
- appointment scheduling and status tracking
- appointment conflict validation
- actual service price tracking per appointment
- financial analytics with filtering
- CSV data export
- audit logging
- REST API endpoints
- Docker-based local deployment
- Railway-based cloud deployment

---

## Backend Design

| Concern | Implementation |
|---|---|
| Organization and role boundaries | [Shared appointment query](src/appointments/querysets.py) applies the same visibility rules to pages, client history, exports, dashboard queries, and the appointment API. |
| Concurrent bookings | [Scheduling helpers](src/appointments/scheduling.py) lock the organization row inside a transaction, then check overlapping appointments before creation, rescheduling, or reactivation. |
| Audit attribution | [Request context](src/audit/context.py) carries the acting user to model signals and is reset after each request or explicit operation. |
| Read-only API | [DRF views](src/api/views.py) expose organization-scoped records; appointment visibility also respects employee assignments. |
| Reproducible verification | [GitHub Actions](.github/workflows/ci.yml) runs the test suite with PostgreSQL, checks migrations, compiles translations, and collects production static files. |

The [case study](docs/portfolio-case-study.md) explains the booking and audit decisions, the tests behind them, and the current tradeoffs.

---

## Screenshots

![English demo dashboard with EUR prices](docs/screenshots/dashboard-preview.jpg)

<details>
<summary>Full dashboard</summary>

![Dashboard](docs/screenshots/dashboard.jpg)

</details>

<details>
<summary>Financial analytics</summary>

![Financial analytics](docs/screenshots/finance.jpg)

</details>

<details>
<summary>Client management</summary>

![Client management](docs/screenshots/clients.jpg)

</details>

<details>
<summary>Dark mode</summary>

![Dark mode](docs/screenshots/dark-mode.jpg)

</details>

<details>
<summary>Service currency selection</summary>

![Currency selected before the base price](docs/screenshots/service-currency.jpg)

</details>

<details>
<summary>Organization time format</summary>

![Organization settings with 12-hour display selected](docs/screenshots/time-format.jpg)

</details>

<details>
<summary>Sign in</summary>

![Sign in](docs/screenshots/sign-in.jpg)

</details>

---

## Prices, currencies, and time display

Choose **UAH**, **EUR**, or **USD** when creating a service, before entering its price. Each service keeps that currency; appointments use the service currency. Amounts are never converted. Create a new service if you need another currency.

Financial analytics filters by currency. Dashboard revenue and client spending show separate currency totals, and CSV exports and API prices include their currency code. Different currencies are never added into a single revenue figure.

Administrators can choose a **12-hour** or **24-hour** display in **Organization settings**. The choice applies across workspace pages and does not change stored times, the time zone, or the ISO formats used in API responses and CSV exports. Native date/time inputs follow the browser's own controls.

---

## Main Features

### Multi-Tenant Architecture

Each organization has its own isolated workspace. Main tenant-related features:

- automatic organization creation during signup
- user-to-organization binding
- organization-scoped clients, services, appointments, audit logs, and analytics
- protection against accessing data from another organization

---

### User Roles

The system supports three main roles:

| Role | Description |
|---|---|
| Admin | Full access: manages organization settings, users, services, clients, appointments, finances, audit logs, and can delete appointments |
| Manager | Manages operational data: clients, services, appointments, and financial analytics |
| Employee | Works with assigned appointments |

Role-based access is enforced in views and querysets, as well as in the visible navigation. Hiding a button is not the access boundary.

---

### Authentication

Users log in using a username, password, and organization name. This prevents users from accessing the wrong organization workspace and supports the multi-tenant structure of the system.

---

### Client Management

- create, edit, activate, and deactivate clients
- search and filter clients
- export client list to CSV

Client records are scoped to the current organization.

---

### Service Management

The service catalog allows users to manage:

- service categories
- services with base price and duration
- active or inactive service status

---

### Appointment Management

- create appointments with client, service, employee, date, and time
- quick status changes from the appointment list
- inline editing of actual appointment price
- appointment conflict validation per employee, repeated under a PostgreSQL row lock for booking changes
- appointment deletion (Admin only) with confirmation modal and audit log entry
- filtering, search, and pagination

---

### Financial Analytics

The financial analytics page (Admin and Manager only) allows analysis by date range, service, and employee. It includes:

- total revenue and average check
- number of paid appointments
- grouped analytics by services and employees
- revenue chart by date with period toggle (week / month / year)
- detailed appointment revenue table
- CSV export of financial data

---

### Dashboard

The dashboard provides a compact overview:

- operational KPIs with month-over-month comparison
- upcoming appointments
- appointment status statistics
- daily revenue summary (Admin and Manager)
- onboarding checklist for new organizations

---

### Onboarding

For newly created organizations the system shows a checklist:

- create the first service category
- create the first service
- add an employee
- add a client
- create the first appointment

---

### Audit Log

The audit module tracks important system events including user actions, entity changes, appointment status changes, and appointment deletions.

---

### CSV Export

CSV export is available for clients, services, appointments, and financial analytics. Exports respect organization boundaries, user roles, and active filters. Files include a BOM marker for correct display of Cyrillic characters in Microsoft Excel.

---

### REST API

Read-only REST API endpoints built with Django REST Framework. Available for clients, services, appointments, and dashboard analytics. Access is restricted to authenticated users with organization-based data isolation.

---

## Technology Stack

### Backend

- Python 3.14
- Django 6.0
- Django REST Framework
- PostgreSQL
- Gunicorn (production WSGI server)
- WhiteNoise (static file serving)
- dj-database-url (Railway DATABASE_URL support)
- python-decouple (environment variable management)
- django-ratelimit (API rate limiting)

### Frontend

- Django Templates
- HTML / CSS / Vanilla JavaScript
- Chart.js 4.4 (served locally, no CDN dependency)

### Database

- PostgreSQL 18
- Organization-scoped relational data model

### Infrastructure

- Docker + Docker Compose (local development)
- Railway (cloud deployment via Dockerfile + railway.toml)
- Environment-based configuration via `.env`

---

## Project Structure

```text
orvanta/
├── Dockerfile
├── railway.toml
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── requirements.txt
├── README.md
└── src/
    ├── manage.py
    ├── seed_salon.py      # Compatibility entry point for setup_demo
    ├── config/           # Django settings, URLs, WSGI, views, utils, CSV export
    ├── users/            # Custom user model, roles, decorators, profile, password change
    ├── clients/          # Client model, views, CSV export
    ├── services_catalog/ # Service categories and services
    ├── appointments/     # Appointments, status flow, conflict validation, deletion
    ├── audit/            # Audit log model and views
    ├── api/              # REST API endpoints (DRF)
    ├── templates/        # All HTML templates
    └── static/           # CSS, JS (including Chart.js), images
```

---

## Languages

English is the default interface language on the first visit. Use **EN / UK** on the sign-in and signup forms. After signing in, administrators can change the language in **Organization settings**; managers and employees can use **Profile → Interface**. The choice is personal to the current browser, even when the control appears in organization settings.

The language is remembered in a browser cookie and applies to pages, forms, validation messages, status labels, and interface controls. Existing application URLs stay the same when switching language.

New demo workspaces use English sample service and client data. Existing demo workspaces remain unchanged on a normal `setup_demo` run; use the documented `--reset` option to replace only the managed demo workspace with fresh English fixtures.

Names, notes, and other content entered by users are stored as entered. Changing the interface language does not rewrite user data or historical audit descriptions.

### Maintaining translations

English interface strings are the source messages; Ukrainian translations live in `src/locale/uk/LC_MESSAGES/`. Python/templates use the `django` catalog, while browser scripts use `djangojs`.

The GNU gettext tools (`xgettext`, `msgmerge`, and `msgfmt`) are required for maintaining catalogs in a native development environment. The Docker build installs gettext and compiles the message catalogs.

From the `src` directory, extract updated strings, edit the Ukrainian `.po` files, and compile them:

```bash
python manage.py makemessages -l uk --ignore=staticfiles --ignore='*/migrations/*'
python manage.py makemessages -d djangojs -l uk --ignore=staticfiles --ignore=chart.umd.min.js
python manage.py compilemessages
```

---

## Local Demo (Docker)

### Requirements

- Docker Engine or Docker Desktop
- Docker Compose with `docker compose up --wait` support
- Local ports `8000` and `5433` available

### Setup

1. Clone the repository:

```bash
git clone https://github.com/Curun1r/Orvanta.git orvanta
cd orvanta
```

2. Copy the example environment file:

```bash
cp .env.example .env
```

Set a random `SECRET_KEY` and a local `DATABASE_PASSWORD` in `.env`. Keep `DEBUG=True`, `DATABASE_HOST=db`, and `ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0` for this Docker demo. Leave `DATABASE_URL` unset so the local PostgreSQL settings are used.

3. Build and start the containers, waiting until the application is ready:

```bash
docker compose up --build --detach --wait --wait-timeout 120
```

PostgreSQL must pass its health check before the web service starts. The web startup command collects static files and applies migrations before starting Gunicorn. The application health check then confirms it is serving requests.

4. Create the demo workspace and sample data:

```bash
docker compose exec web python src/manage.py setup_demo
```

This command creates an English-language demo with fictional client and staff names and **EUR** service prices. It creates **Orvanta Demo** (`orvanta-demo`), accounts for all three roles, 35 sample clients, 30 services, and 180 appointments around the current date. Past completed appointments populate financial analytics; upcoming appointments populate the dashboard.

A shared password is generated and printed when the demo accounts are created. Save it for the following logins:

| Role | Username | Organization |
|---|---|---|
| Admin | `demo_admin` | `orvanta-demo` |
| Manager | `demo_manager` | `orvanta-demo` |
| Employee | `demo_emma` | `orvanta-demo` |

The other employee accounts are `demo_olivia`, `demo_james`, `demo_sophie`, and `demo_daniel`; they use the same demo password and organization.

Open [http://localhost:8000/login/](http://localhost:8000/login/) and enter the username, generated password, and organization slug. The application admin account is ready to use; creating a Django superuser is not required.

For a local demo with a password you choose, provide it on initial setup:

```bash
docker compose exec web python src/manage.py setup_demo --password 'LocalDemo2026!'
```

For a new demo using another currency, choose it before the services are generated:

```bash
docker compose exec web python src/manage.py setup_demo --currency USD
```

`EUR` is the default; `UAH` and `USD` are also available. These are independent fictional price lists, not exchange-rate conversions. To replace an older managed demo with the current English/EUR fixtures, use `setup_demo --reset --currency EUR`. This replaces only the managed demo workspace and its credentials.

### Repeat or refresh the demo

Running `setup_demo` again leaves existing demo data and passwords unchanged. It does not add another set of appointments or select an existing business organization.

To rebuild the dedicated demo workspace with dates relative to today and new credentials:

```bash
docker compose exec web python src/manage.py setup_demo --reset
```

Reset removes changes made inside the managed demo workspace. Other organizations are preserved. Setup refuses conflicting organization names or usernames instead of reusing another organization's accounts.

The legacy `python src/seed_salon.py` entry point runs the same demo setup command.

### Suggested walkthrough

1. Sign in as `demo_admin` and inspect the dashboard, upcoming appointments, clients, and service catalog.
2. Open **Finance** to inspect completed-appointment revenue and export a filtered CSV.
3. Create an appointment, then attempt another appointment for the same employee at an overlapping time to see conflict validation.
4. Sign in as `demo_emma`. Appointment lists, API responses, and client appointment history are limited to this employee's assigned records.
5. Sign in as `demo_manager` to manage operational data; sign in as `demo_admin` to inspect user management and the audit log.

### Start with your own organization

Open [http://localhost:8000/signup/](http://localhost:8000/signup/) to create a separate organization with your own administrator account. The demo command is optional and does not populate that organization.

For developer access to Django admin at `/orvanta-admin/`, create a separate superuser:

```bash
docker compose exec web python src/manage.py createsuperuser
```

### Stop or inspect the local application

```bash
docker compose logs --tail=100 web
docker compose stop
```

Stopping the services preserves PostgreSQL data. Starting them again with `docker compose up --detach --wait` reuses the existing database.

### Tests

The [CI workflow](.github/workflows/ci.yml) runs the full suite on PostgreSQL 18 with Python 3.14, including the concurrent booking tests. It also checks for missing migrations, compiles translation catalogs, and collects production static files.

For a local run with in-memory SQLite:

```bash
docker compose exec --workdir /app/src web python manage.py test --settings=config.test_settings
```

For an existing native Python environment, run from the `src` directory:

```bash
cd src
python manage.py test --settings=config.test_settings
```

SQLite skips the three PostgreSQL-specific concurrency tests; it does not verify row-locking behavior.

To run the complete suite locally, use a disposable PostgreSQL instance. For example, start a separate container with test-only credentials and check that it is ready:

```bash
docker run --detach --rm --name orvanta-test-db \
  -e POSTGRES_DB=orvanta_ci \
  -e POSTGRES_USER=orvanta_ci \
  -e POSTGRES_PASSWORD=orvanta_ci \
  -p 127.0.0.1:5434:5432 postgres:18
docker exec orvanta-test-db pg_isready -U orvanta_ci -d orvanta_ci
```

Once PostgreSQL is ready, run from `src` in an environment with the project dependencies and compiled translations:

```bash
DATABASE_URL=postgresql://orvanta_ci:orvanta_ci@localhost:5434/orvanta_ci \
  python manage.py test --settings=config.test_postgres_settings --noinput
```

These settings require an explicit PostgreSQL `DATABASE_URL` and use the dedicated test database `test_orvanta_ci`. Use the disposable server above, not a production database. Stop it after testing:

```bash
docker stop orvanta-test-db
```

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Django secret key | `long-random-string` |
| `DEBUG` | Debug mode | `True` / `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `DATABASE_URL` | Full DB URL (used on Railway) | `postgresql://user:pass@host/db` |
| `DATABASE_NAME` | DB name (local only) | `orvanta_db` |
| `DATABASE_USER` | DB user (local only) | `orvanta_user` |
| `DATABASE_PASSWORD` | DB password (local only) | `secret` |
| `DATABASE_HOST` | DB host (local only) | `db` |
| `DATABASE_PORT` | DB port (local only) | `5432` |
| `RATELIMIT_ENABLE` | Enable API rate limiting | `True` / `False` |

---

## Cloud Deployment (Railway)

The project is configured for deployment on [Railway](https://railway.app) using Docker.

1. Push the repository to GitHub.
2. Create a new project on Railway and connect the GitHub repository.
3. Add a PostgreSQL plugin — Railway will provide `DATABASE_URL` automatically.
4. Set the required environment variables: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`.
5. Railway will build the Docker image and run migrations automatically on each deploy.
