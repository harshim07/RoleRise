# RoleRise — Candidate Job Portal

A Dockerized, candidate-only job portal built with React, TypeScript, Vite, FastAPI, SQLAlchemy, Alembic, and PostgreSQL. Jobs and application status history are stored locally as assignment/demo ATS data. A backend job-catalog service boundary makes it possible to replace the local catalog with a company ATS adapter when API credentials and documentation become available.

## Run locally with Docker

1. Copy `.env.example` to `.env`.
2. Set `POSTGRES_PASSWORD` to a strong database password and `JWT_SECRET` to a random secret of at least 32 characters.
3. Run:

   ```powershell
   docker compose up --build
   ```

4. Open [http://localhost:5173](http://localhost:5173). FastAPI's interactive docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

PostgreSQL health checks gate backend startup; Alembic migrations run before the API starts. PostgreSQL data and PDF/DOCX resumes persist in named Docker volumes. To stop the services without removing data, press Ctrl+C and run `docker compose down`.

## Demo account and sample ATS data

Set `DEMO_PASSWORD` in `.env` to a unique password of at least 12 characters, then run:

```powershell
docker compose exec backend python -m app.seed
```

This idempotently creates `candidate@example.com`, 27 sample local jobs across engineering, product, design, data, marketing, sales, operations, and other disciplines, plus application history examples for three roles. The sample records demonstrate `Applied`, `Under Review`, `Shortlisted`, `Interview Scheduled`, `Selected`, and `Rejected` across current statuses and history; the candidate can also withdraw an eligible application. Change the demo password before any non-local use.

Public registration creates candidate accounts only. There is no recruiter registration, recruiter dashboard, job creation UI, or recruiter API.

## Candidate features

- Candidate registration, login, logout, hashed passwords, and expiring JWT authentication.
- Single-use password-reset links with configurable SMTP delivery.
- Candidate profile, completion percentage, skills, education, work history, social links, and role/work-mode/salary/notice preferences.
- Private PDF or DOCX resume upload, preview, replacement, removal, and parsing of name, contact details, location, summary, and skills; parsed skills feed job recommendations. Files are limited to 5 MB.
- Local job listing/search with location, skill, experience, and employment-type filters, sorting, and pagination.
- Profile-based job recommendations and skill/preference match tags, saved jobs, and saved-search job alerts.
- Applications with screening answers, optional notes, resume/contact snapshots, and duplicate/closed-job protection.
- Dashboard stats, application status/history tracking, interview time selection, offer acceptance, permitted withdrawals, and timestamped notifications.

## API overview

All routes are prefixed with `/api`.

| Area | Routes |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/forgot-password`, `POST /auth/reset-password` |
| Profile | `GET/PUT /profile`, `POST/GET/DELETE /profile/resume`, education and experience add/edit/remove routes |
| Job discovery | `GET /jobs`, `GET /jobs/{id}`, `GET /recommendations` |
| Candidate actions | `POST/DELETE /jobs/{id}/save`, `GET /saved-jobs`, `POST /jobs/{id}/apply`, saved-search alert routes |
| Tracking | `GET /applications`, `GET /applications/{id}/status`, `GET /applications/{id}/history`, withdraw/interview/offer actions, notifications, and dashboard routes |

Candidates can only access their own profiles, resumes, applications, application history, saved jobs, saved searches, and notifications. This repository does not include credentials or an API contract for a real company ATS/CRM. The local mock ATS is the source of truth for demo application statuses, interview slots, offers, and status history; candidates can view this data and withdraw eligible applications but cannot change hiring decisions.

## Development

- Frontend: `cd frontend; npm install; npm run dev`
- Backend dependencies: `cd backend; python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt`
- Backend server (with PostgreSQL available): `cd backend; alembic upgrade head; uvicorn app.main:app --reload`
- Frontend production build: `cd frontend; npm run build`
- Backend tests: `cd backend; pytest`
- Frontend tests: `cd frontend; npm test`

Set `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, and `UPLOAD_DIR` for local backend development. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` in `.env` to deliver reset links. Without SMTP, password-reset requests return an explicit configuration error. Never use development secrets in production.

## ATS integration seam

`backend/app/services/ats.py` defines the `ATSAdapter` contract and `MockATSService` implementation. Application submission, status reads, status history, withdrawals, interview bookings, and offer decisions pass through this boundary; the mock service persists the simulated ATS responses in the local application and history tables. Its sample meeting URLs use the reserved `example.com` domain and are not real meeting rooms. When Jobs Territory provides API access, replace the mock adapter with a vendor adapter rather than replacing the candidate portal.

`backend/app/services/jobs.py` defines the `JobCatalog` interface. New jobs ingested into the mock catalog are checked against active saved searches and create candidate notifications for matches. Profile resume parsing is in `backend/app/services/resumes.py`; parsed skills participate in personalized recommendations.

Presentation note: “We are not replacing the existing ATS. We are building a candidate-facing interface that communicates with it.”

## Security notes

Use unique random JWT and database secrets. Access tokens expire after 12 hours and logout/password reset revoke existing tokens. Production deployments should terminate TLS at a trusted reverse proxy, set exact allowed CORS origins, configure SMTP, and apply operational rate limits.
