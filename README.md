# Career Engine Backend

FastAPI backend for Career Engine with a Django-style project layout.

Main features:

1. Persist user resume data (personal info, education, projects, skills) in Postgres.
2. Login users with Google OAuth web flow.
3. Generate a brand new Google Doc resume from stored resume payload using Google Docs API.

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   └── v1/
│   │       ├── api.py
│   │       └── endpoints/
│   ├── core/
│   ├── crud/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   └── services/
├── tests/
├── alembic/
│   └── versions/
├── alembic.ini
├── main.py                    # ASGI app export (app.main:app)
└── pyproject.toml
```

## Prerequisites

1. Python 3.12+
2. `uv` installed
3. Postgres database
4. Google OAuth Web application credentials from Google Cloud (client ID + client secret)

## Environment

Copy `.env.example` to `.env` and fill values.

Required variables:

1. `DATABASE_URL`
2. `GOOGLE_CLIENT_ID` (OAuth web client id)
3. `GOOGLE_CLIENT_SECRET` (OAuth web client secret)
4. `GOOGLE_REDIRECT_URI`
5. `FRONTEND_ORIGIN`
6. `ENCRYPTION_KEY` (Fernet key)

Generate Fernet key:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Install Dependencies

```bash
uv sync
```

## Database Migrations

```bash
uv run alembic upgrade head
```

## Run API

```bash
uv run uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/healthz
```

## API Overview

Base path: `/api/v1`

1. `GET /auth/google/login/start`
	- Returns Google authorization URL + state for login.
2. `GET /auth/google/login/callback?state=...&code=...`
	- Verifies Google identity, stores encrypted Google credentials, sets HttpOnly session cookie, redirects to frontend.
3. `GET /auth/me`
	- Returns current session user.
4. `POST /auth/logout`
	- Clears the session cookie and invalidates server session.
5. `GET /auth/google/start`
	- Requires authenticated session cookie.
	- Starts Google reconnect flow for already logged-in user.
6. `GET /auth/google/callback?state=...&code=...`
	- Stores refreshed encrypted Google credentials for the logged-in user.
7. `POST /projects/autofill`
	- Generates project suggestions from a GitHub repository URL.
8. `POST /projects/tailor`
	- Tailors selected saved projects to a job using GitHub scan + LLM generation.
9. `POST /resumes`
	- Requires authenticated session cookie.
	- Creates a resume record.
10. `GET /resumes/{resume_id}`
11. `PATCH /resumes/{resume_id}`
12. `DELETE /resumes/{resume_id}`
13. `POST /resumes/{resume_id}/generate-doc`
	- Creates a new Google Doc resume from stored payload.

Generated document URL format:

`https://docs.google.com/document/d/{document_id}/edit`

## Notes

1. This implementation uses an HttpOnly cookie session for short-lived login.
2. Session duration defaults to 1 hour (`SESSION_TTL_SECONDS`).
3. Keep OAuth credentials and secrets out of version control.
