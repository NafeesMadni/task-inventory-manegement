# Inventory Manager

> **All commands in this guide are for Ubuntu.** On another system, install the same tools with your package manager.

Device inventory portal with role-based access (admin, supervisor, developer), device requests and approvals, login history, Google sign-in, and voice input for adding devices.

## Stack

- FastAPI
- SQLAlchemy async ORM with `asyncpg`
- Alembic async migrations
- PostgreSQL (local or hosted, including Supabase)
- Redis, used by Celery and the login rate limiter
- Celery for background jobs (voice transcription, email and reminders)
- Whisper for speech-to-text (runs locally)
- OpenRouter for the LLM that structures the transcript
- Google OAuth2 and Cloudflare Turnstile
- Pydantic Settings for environment-based configuration

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL
- Redis
- ffmpeg (needed by Whisper)

Install everything on Ubuntu:

```bash
sudo apt update
sudo apt install -y postgresql redis-server ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo systemctl enable --now postgresql redis-server
```

Create the database (change the password to your own):

```bash
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'password';"
sudo -u postgres createdb app_db
```

## Setup

```bash
uv sync
cp .env.example .env
```

Fill in `.env`:

```dotenv
APP_NAME=Inventory Manager

DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/app_db

# JWT credentials
SECRET_KEY=               # HS256 secret: https://randomkeygen.com/jwt-secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM=HS256

# Gmail SMTP
GMAIL_PORT=587
GMAIL_HOST=smtp.gmail.com
GMAIL_USER=
GMAIL_PASSWORD=           # a Gmail app password, not your normal password

# 2FA 
TWO_FACTOR_ENCRYPTION_KEY= # uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Initial admin account
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=your-strong-password

# Celery
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# Google OAuth2
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
SESSION_SECRET=           # openssl rand -hex 32

# Cloudflare Turnstile
TURNSTILE_SITE_KEY= # Public key for frontend
TURNSTILE_SECRET_KEY=
SITEVERIFY_URL=https://challenges.cloudflare.com/turnstile/v0/siteverify

# OpenRouter
OPENROUTER_API_KEY=
```

- **`DATABASE_URL`**: `postgres://` and `postgresql://` URLs are accepted and converted to the `asyncpg` dialect. For Supabase, use the connection string from the project's **Connect** dialog. URL-encode special characters in the password, and keep credentials out of source control.
- **Google OAuth2**: in the Google Cloud console, add `http://localhost:8000/api/v1/user/auth/callback` as an authorized redirect URI.
- **Turnstile**: create a widget in the Cloudflare dashboard. The secret key goes in `.env`. The matching site key goes in `data-sitekey` in `signin.html` and `signup.html`. How the server validates the token: [Turnstile server-side validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/#basic-validation-examples).

## Whisper (local speech-to-text)

Whisper runs inside the Celery worker, so it needs `ffmpeg` (installed above) and its Python package (installed by `uv sync`). Download the model once, so the first voice request isn't slow:

```bash
uv run python -c "import whisper; whisper.load_model('base')"
```

The model is cached in `~/.cache/whisper`. The model size is set where the transcription task is called (`model_type="base"`). Larger models (`small`, `medium`) are more accurate, especially for Urdu, but slower.

## Database

### First start

Create the first revision, check it, and push it to head:

```bash
uv run alembic revision --autogenerate -m "initial"
uv run alembic upgrade head
```

If `migrations/versions/` already contains revisions, skip the first command and only run `upgrade head`.

### After changing a model

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

Always review the generated migration before applying it.

## Run

API (terminal 1):

```bash
uv run fastapi dev app/main.py
```

Celery worker (terminal 2, Redis must be running):

```bash
uv run celery -A app.core.celery worker --loglevel=INFO
```

The app is at `http://127.0.0.1:8000`, the API docs at `/docs`, and a basic health check at `GET /api/health`.
