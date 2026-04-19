# Career Engine Backend API (Frontend Guide)

This document describes how the frontend should integrate with the Career Engine FastAPI backend.

- API version prefix: `/api/v1`
- Auth mechanism: **HttpOnly cookie session** (backend sets `ce_session` by default)
- Primary login: **Google OAuth web flow** (browser redirects)

## Base URL

In local dev (default settings):

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

All API paths in this doc are relative to the backend base URL.

## CORS + cookies (important)

The backend enables CORS with:

- `allow_origins = [FRONTEND_ORIGIN]`
- `allow_credentials = true`

### Frontend HTTP client rule

All requests that require authentication must include credentials so the browser sends the session cookie:

- `fetch(..., { credentials: "include" })`
- `axios.create({ withCredentials: true })`

### Cookie attributes

On successful login the backend sets a cookie:

- Name: `SESSION_COOKIE_NAME` (default `ce_session`)
- HttpOnly: `true` (JS cannot read it)
- Path: `/`
- SameSite: `COOKIE_SAMESITE` (default `lax`)
- Secure: `COOKIE_SECURE` OR `APP_ENV != development`

Notes:

- Because the cookie is **HttpOnly**, the frontend should use `GET /api/v1/auth/me` to check login state.
- If you deploy frontend and backend on **different “sites”** (different registrable domains), `SameSite=lax` will typically prevent the cookie being sent on XHR/fetch. In that case you usually need `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` (and HTTPS). This backend supports configuring those values.

## Common response/error format

- Successful responses are JSON (except `204 No Content`).
- Errors use FastAPI’s default shape:

```json
{ "detail": "..." }
```

Common auth errors:

- `401 Not authenticated` → missing session cookie
- `401 Invalid session` / `Session expired` → cookie present but not valid

## Health

### `GET /healthz`

Simple health check.

Response `200`:

```json
{ "status": "ok" }
```

## Authentication

There are two distinct OAuth-related concepts:

1. **Login** (`/auth/google/login/*`): creates a backend session cookie and logs the user into this API.
2. **Google connection** (`/auth/google/*`): (re)connects Google credentials for an already logged-in user.

In practice, the login flow already stores Google credentials as part of the callback, so most apps only need the “connect” flow for re-consent / reconnect.

### Login flow (Google)

#### 1) Start login

`GET /api/v1/auth/google/login/start`

Query params:

- `next` (optional): where the backend should redirect the browser after successful login.
  - Allowed values:
    - Relative paths like `/dashboard`
    - Absolute URLs **only if same-origin as** `FRONTEND_ORIGIN`
  - Any other origin will be rejected and replaced with `FRONTEND_ORIGIN`.

Response `200`:

```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "<uuid>"
}
```

Frontend behavior:

- Navigate the browser to `authorization_url` (full-page redirect).

#### 2) OAuth callback (backend)

`GET /api/v1/auth/google/login/callback?state=...&code=...`

- This endpoint is meant to be hit by Google redirecting back to your backend.
- On success:
  - backend creates/loads the user
  - stores encrypted Google credentials
  - creates a backend session
  - **sets the session cookie**
  - **redirects (302) to `next`** (or to `FRONTEND_ORIGIN`)

Frontend behavior:

- Your SPA route at the `next` location can immediately call `GET /api/v1/auth/me` to confirm the user.

### Session introspection

#### `GET /api/v1/auth/me`

Requires: authenticated session cookie.

Response `200`:

```json
{ "user_id": "<uuid>", "email": "user@example.com" }
```

Common errors:

- `401` with `{ "detail": "Not authenticated" }`

### Logout

#### `POST /api/v1/auth/logout`

Requires: cookie (if present, it will be invalidated server-side).

Response `200`:

```json
{ "success": true }
```

Also clears the cookie on the response.

### (Re)connect Google account (optional)

These endpoints require an authenticated backend session.

#### Start connect

`GET /api/v1/auth/google/start`

Response `200`:

```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "<uuid>"
}
```

Frontend behavior:

- Full-page redirect to `authorization_url`.

#### Connect callback

`GET /api/v1/auth/google/callback?state=...&code=...`

Response `200`:

```json
{ "user_id": "<uuid>", "email": "user@example.com", "connected": true }
```

Notes:

- Unlike login callback, this one returns JSON (no redirect), so your frontend can choose whether to handle it via a dedicated route or by simply initiating the flow and letting the backend response be shown.

## Profile

Profile endpoints manage account-tied personal information.

All profile endpoints require an authenticated session cookie.

There is exactly one profile per user.

### Profile shape

```json
{
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "phone": "+1 555 0100",
  "address": "City, ST",
  "github_label": "GitHub",
  "github_url": "https://github.com/ada"
}
```

- `github_label` is optional (defaults to `"GitHub"`).
- `github_url` is optional.

### Get profile

#### `GET /api/v1/profile`

Response `200`:

```json
{
  "id": "<profile_id>",
  "user_id": "<user_id>",
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "phone": "+1 555 0100",
  "address": "City, ST",
  "github_label": "GitHub",
  "github_url": "https://github.com/ada",
  "created_at": "2026-01-01T12:34:56.000Z",
  "updated_at": "2026-01-01T12:34:56.000Z"
}
```

Errors:

- `404 { "detail": "Profile not found" }` if profile has not been created yet.

### Create or replace profile

#### `PUT /api/v1/profile`

Request:

```json
{
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "phone": "+1 555 0100",
  "address": "City, ST",
  "github_label": "GitHub",
  "github_url": "https://github.com/ada"
}
```

Response `200`: same shape as `GET /api/v1/profile`.

## Educations

Education endpoints manage an ordered list of education entries per user.

All education endpoints require an authenticated session cookie.

### Education item shape

```json
{
  "university": "Example University",
  "degree": "B.S.",
  "field": "Computer Science",
  "time_period": "2020-2024",
  "gpa": "3.9",
  "location": "City, ST",
  "relevant_coursework": "Algorithms, Systems"
}
```

Optional fields: `gpa`, `location`, `relevant_coursework`.

### List educations

#### `GET /api/v1/educations`

Response `200`:

```json
[
  {
    "id": "<education_id>",
    "user_id": "<user_id>",
    "sort_order": 0,
    "university": "Example University",
    "degree": "B.S.",
    "field": "Computer Science",
    "time_period": "2020-2024",
    "gpa": "3.9",
    "location": "City, ST",
    "relevant_coursework": "Algorithms, Systems",
    "created_at": "2026-01-01T12:34:56.000Z",
    "updated_at": "2026-01-01T12:34:56.000Z"
  }
]
```

Items are sorted by `sort_order` ascending, then `created_at` ascending.

### Create education

#### `POST /api/v1/educations`

Request:

```json
{
  "university": "Example University",
  "degree": "B.S.",
  "field": "Computer Science",
  "time_period": "2020-2024",
  "gpa": "3.9",
  "location": "City, ST",
  "relevant_coursework": "Algorithms, Systems",
  "sort_order": 0
}
```

- `sort_order` is optional. If omitted, backend appends to the end of the user list.

Response `201`: one `EducationResponse` object.

### Update education

#### `PATCH /api/v1/educations/{education_id}`

Request supports partial updates, including `sort_order`.

Response `200`: updated `EducationResponse` object.

Errors:

- `404 { "detail": "Education not found" }` if missing or not owned by current user.

### Delete education

#### `DELETE /api/v1/educations/{education_id}`

Response `204 No Content`.

## Projects

Project endpoints manage an ordered list of project entries per user.

All project endpoints require an authenticated session cookie.

### Project item shape

```json
{
  "title": "My Project",
  "date_range": "Jan 2024 - Mar 2024",
  "github_url": "https://github.com/org/repo",
  "tech_stack": "FastAPI, Postgres",
  "bullets": ["Did X", "Improved Y"]
}
```

Optional fields: `github_url`, `tech_stack`. `bullets` defaults to `[]`.

### List projects

#### `GET /api/v1/projects`

Response `200`: array of `ProjectResponse` objects.

Items are sorted by `sort_order` ascending, then `created_at` ascending.

### Create project

#### `POST /api/v1/projects`

Request:

```json
{
  "title": "My Project",
  "date_range": "Jan 2024 - Mar 2024",
  "github_url": "https://github.com/org/repo",
  "tech_stack": "FastAPI, Postgres",
  "bullets": ["Did X", "Improved Y"],
  "sort_order": 0
}
```

- `sort_order` is optional. If omitted, backend appends to the end of the user list.

Response `201`: one `ProjectResponse` object.

### Update project

#### `PATCH /api/v1/projects/{project_id}`

Request supports partial updates, including `sort_order`.

Response `200`: updated `ProjectResponse` object.

Errors:

- `404 { "detail": "Project not found" }` if missing or not owned by current user.

### Delete project

#### `DELETE /api/v1/projects/{project_id}`

Response `204 No Content`.

### Autofill project from GitHub URL

#### `POST /api/v1/projects/autofill`

Use this endpoint to preview project details from a public GitHub repository before saving.

Request:

```json
{
  "github_url": "https://github.com/org/repo"
}
```

Response `200`:

```json
{
  "title": "Career Engine Backend",
  "date_range": "Jan 2024 - Present",
  "github_url": "https://github.com/org/repo",
  "tech_stack": "Python, FastAPI, PostgreSQL, Docker",
  "bullets": [
    "Built modular APIs for resume and project workflows with an async service architecture.",
    "Implemented authenticated session and OAuth integrations to secure user-specific operations.",
    "Improved maintainability by organizing typed schemas, CRUD layers, and reusable service modules."
  ]
}
```

Notes:

- This endpoint does not create or update database records.
- Use `POST /api/v1/projects` after user confirmation to save the autofilled content.
- Title and date range are inferred from GitHub README and commit history.
- Tech stack and bullet points are generated from repository code scan via LangChain GitHub loader + configured LLM provider.
- `GITHUB_TOKEN` must be configured for repository code scanning in the LangChain loader.
- Default LLM provider is Mistral (`PROJECT_AUTOFILL_LLM_PROVIDER=mistral`) and can be switched to OpenAI or Gemini.

Errors:

- `422` for invalid or non-GitHub URL input.
- `404` when repository is not found or inaccessible.
- `429` when GitHub API rate limit is reached.
- `503` when selected LLM provider key is missing.
- `502` for upstream GitHub/LLM failures.

## Resume from Scratch

The resume flow remains independent and unchanged: frontend still sends complete resume payloads directly when creating/updating resumes.

## Resumes

All resume endpoints require an authenticated session cookie.

### Data model (ResumePayload)

A resume has:

- `title`: string
- `payload`: object with:
  - `personal_info`
  - `education[]`
  - `projects[]`
  - `skills[]`

#### `personal_info`

```json
{
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "phone": "+1 555 0100",
  "address": "City, ST",
  "github_label": "GitHub",
  "github_url": "https://github.com/ada"
}
```

- `github_label` is optional (defaults to `"GitHub"`).
- `github_url` is optional.

#### `education[]` item

```json
{
  "university": "Example University",
  "degree": "B.S.",
  "field": "Computer Science",
  "time_period": "2020–2024",
  "gpa": "3.9",
  "location": "City, ST",
  "relevant_coursework": "Algorithms, Systems"
}
```

Optional fields: `gpa`, `location`, `relevant_coursework`.

#### `projects[]` item

```json
{
  "title": "My Project",
  "date_range": "Jan 2024 – Mar 2024",
  "github_url": "https://github.com/org/repo",
  "tech_stack": "FastAPI, Postgres",
  "bullets": ["Did X", "Improved Y"]
}
```

Optional fields: `github_url`, `tech_stack`. `bullets` defaults to `[]`.

#### `skills[]` item

```json
{ "label": "Languages", "values": "Python, TypeScript" }
```

### Create a resume

#### `POST /api/v1/resumes`

Request:

```json
{
  "title": "Software Engineer Resume",
  "payload": {
    "personal_info": {
      "full_name": "Ada Lovelace",
      "email": "ada@example.com",
      "phone": "+1 555 0100",
      "address": "City, ST",
      "github_label": "GitHub",
      "github_url": "https://github.com/ada"
    },
    "education": [],
    "projects": [],
    "skills": []
  }
}
```

Response `201`:

```json
{
  "id": "<resume_id>",
  "user_id": "<user_id>",
  "title": "Software Engineer Resume",
  "payload": { "...": "..." },
  "created_at": "2026-01-01T12:34:56.000Z",
  "updated_at": "2026-01-01T12:34:56.000Z"
}
```

### Fetch a resume

#### `GET /api/v1/resumes/{resume_id}`

Response `200`: same shape as above.

Errors:

- `404 { "detail": "Resume not found" }` if the resume doesn’t exist or isn’t owned by the current user.

### Update a resume

#### `PATCH /api/v1/resumes/{resume_id}`

Request supports partial updates:

- `title` optional
- `payload` optional

Example (update title only):

```json
{ "title": "Updated Title" }
```

Example (update payload):

```json
{
  "payload": {
    "personal_info": {
      "full_name": "Ada Lovelace",
      "email": "ada@example.com",
      "phone": "+1 555 0100",
      "address": "City, ST",
      "github_label": "GitHub",
      "github_url": "https://github.com/ada"
    },
    "education": [],
    "projects": [],
    "skills": []
  }
}
```

Response `200`: updated resume.

### Delete a resume

#### `DELETE /api/v1/resumes/{resume_id}`

Response `204 No Content`.

### Generate Google Doc from a resume

#### `POST /api/v1/resumes/{resume_id}/generate-doc`

Request:

```json
{ "document_title": "Ada Lovelace — Resume" }
```

- `document_title` is optional; if omitted, the backend uses the resume `title`.

Response `200`:

```json
{
  "document_id": "<google_doc_id>",
  "document_url": "https://docs.google.com/document/d/<google_doc_id>/edit"
}
```

Common errors:

- `400 { "detail": "Google account not connected for this user" }`
- `401 { "detail": "Google token refresh failed. Reconnect Google account." }`

## Frontend integration snippets

### `fetch` helper

```ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = "Request failed";
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
```

### Start login

```ts
const { authorization_url } = await api<{ authorization_url: string; state: string }>(
  `/api/v1/auth/google/login/start?next=${encodeURIComponent("/dashboard")}`,
  { method: "GET" },
);

window.location.href = authorization_url;
```

### Check session

```ts
try {
  const me = await api<{ user_id: string; email: string }>("/api/v1/auth/me");
  console.log("Logged in as", me.email);
} catch (e) {
  console.log("Not logged in");
}
```
