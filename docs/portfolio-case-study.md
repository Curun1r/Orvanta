# Orvanta: Backend Case Study

**Context:** bachelor's thesis project for managing service businesses.

**Role:** backend and full-stack implementation.

**Stack:** Python, Django, PostgreSQL, Django REST Framework, Docker, Django templates, and vanilla JavaScript.

[Repository overview and screenshots](../README.md) · [Run the demo](../README.md#local-demo-docker)

## The problem

A small service business needs a shared view of clients, services, employee appointments, and revenue. Different people need different access: an administrator manages the workspace, a manager handles operations, and an employee works with assigned appointments. Once several businesses use the same application, those workflows must also keep each organization's data separate.

Orvanta brings these workflows into one web application. The engineering work focuses on making the same rules hold across the interface, exports, and API, including when requests arrive at the same time.

## Architecture and access boundaries

The application uses a shared PostgreSQL database with organization-linked models. Signing up creates an organization and its administrator. Business queries are scoped to the signed-in user's organization; appointment queries additionally restrict employees to their own assigned records.

Appointment visibility is defined in one shared query function. The appointment list, client history, dashboard, CSV exports, and appointment API reuse it. This addresses a practical access-control failure: a record hidden in one page could otherwise remain visible through another route. Role checks also protect write operations; navigation controls reflect those permissions.

Django REST Framework provides authenticated, read-only endpoints for clients, services, appointments, and dashboard analytics. The server-rendered workflows handle business changes.

## Preventing double booking

A form-level overlap check alone is insufficient when two requests both read an available time before either saves. Booking changes therefore run inside a database transaction and acquire a PostgreSQL row lock on the organization before reading the schedule and validating the requested slot.

The same mechanism covers creation, rescheduling, and reactivation of cancelled appointments. Conflicts compare the employee, date, and intersecting time intervals; cancelled appointments do not occupy a slot. A rejected change returns a validation message instead of creating an overlapping booking.

The organization-level lock is deliberately coarse: it provides a clear consistency boundary for this application's scale, while serializing booking changes within each organization. A busier deployment would need measured workloads before choosing finer locking or a database exclusion constraint.

## Recording the actual actor

Audit records must identify the person performing a change, rather than infer that person from the edited record's creator. A request context carries the acting user to model signals and resets the context afterwards. Explicit operations can supply their own context, and events without an authenticated actor remain unattributed.

Tests cover attribution across requests, asynchronous context isolation, and account deletion. The audit log also records authentication and appointment-related events within organization boundaries.

## Verification and demonstration

The test suite exercises organization isolation, role permissions, API responses, exports, language preferences, audit attribution, and demo setup. PostgreSQL tests issue concurrent requests for creation, reactivation, and rescheduling, checking that only one active appointment occupies the conflicting slot.

GitHub Actions runs the suite against PostgreSQL, checks for missing migrations, compiles translation catalogs, and collects production static files. A separate integration test verifies hashed assets, gzip responses, cache headers, and authentication page rendering with `DEBUG=False`.

The Docker demo generates synthetic clients, services, and appointments around the current date. It includes accounts for all three roles. Repeating setup preserves existing data; an explicit reset refreshes only the managed demo workspace. English is the default interface language, with Ukrainian available as a browser preference.

## Scope and outcome

Orvanta demonstrates a complete backend workflow: scoped data access, validated transactional writes, audit attribution, a read-only API, and reproducible verification. It remains a thesis and portfolio application. Its tests establish specific behavior; they do not establish production capacity or measured performance under customer traffic.
