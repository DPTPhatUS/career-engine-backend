# Career Engine Backend

FastAPI backend for Career Engine with a Django-style project layout.

Main features:

1. Persist user resume data (personal info, education, projects, skills) in Postgres.
2. Connect each user to Google via OAuth web flow.
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

1. Python 3.11+
2. `uv` installed
3. Postgres database
4. Google OAuth client credentials JSON (`credentials.json`) created as a **Web application** in Google Cloud

## Environment

Copy `.env.example` to `.env` and fill values.

Required variables:

1. `DATABASE_URL`
2. `GOOGLE_CLIENT_SECRETS_FILE`
3. `GOOGLE_REDIRECT_URI`
4. `FRONTEND_ORIGIN`
5. `ENCRYPTION_KEY` (Fernet key)

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

1. `GET /auth/google/start`
	- Requires header: `X-User-Email`
	- Returns Google authorization URL + state.
2. `GET /auth/google/callback?state=...&code=...`
	- Stores encrypted Google credentials for the user.
3. `POST /resumes`
	- Requires header: `X-User-Email`
	- Creates a resume record.
4. `GET /resumes/{resume_id}`
5. `PATCH /resumes/{resume_id}`
6. `DELETE /resumes/{resume_id}`
7. `POST /resumes/{resume_id}/generate-doc`
	- Creates a new Google Doc resume from stored payload.

Generated document URL format:

`https://docs.google.com/document/d/{document_id}/edit`

## Notes

1. This implementation uses `X-User-Email` as a temporary identity mechanism for development.
2. Replace it with your real app auth (JWT/session) for production.
3. Keep `credentials.json` out of version control.