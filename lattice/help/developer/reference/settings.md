---
title: Settings
summary: Every LATTICE_ environment variable, its default and what it does.
order: 40
keywords: environment variables configuration env oidc sso
---

> [!NOTE]
> Generated from `lattice/kernel/config.py` by `lattice docs build`. Change the code, not this page.

Every setting is an environment variable named LATTICE_ plus the field name in capitals.
Values are read from the environment, then from a `.env` file in the working folder.

| Variable | Default | Description |
|---|---|---|
| `LATTICE_APP_NAME` | `Lattice` | Name shown in the top bar, page titles and the sign-in page. |
| `LATTICE_APP_ENV` | `development` | `development`, `test` or `production`. Production turns off the API docs page, seed data and the showcase job loop, and turns on secure cookies. |
| `LATTICE_BRAND_LOGO_LIGHT` | `/static/brand/logo-light.svg` | Logo for light mode, shown in the top bar and on the sign-in page. |
| `LATTICE_BRAND_LOGO_DARK` | `/static/brand/logo-dark.svg` | Logo for dark mode. |
| `LATTICE_BRAND_SHOW_NAME` | `true` | Show the app name next to the logo. Set false when the logo images already contain the name. |
| `LATTICE_SECRET_KEY` | `dev-secret-change-me` | Signs the flash and OIDC cookies. Set a long random value in production. |
| `LATTICE_DATABASE_URL` | `postgresql+psycopg://lattice:lattice@127.0.0.1:5436/lattice` | The Postgres database, as a SQLAlchemy URL with the psycopg driver. |
| `LATTICE_HOST` | `showcase_host.main:app` | The host the `lattice` command line runs and seeds, as `module:attribute`. |
| `LATTICE_SESSION_IDLE_MINUTES` | `480` | A session ends after this many minutes without a request. |
| `LATTICE_SESSION_MAX_HOURS` | `24` | A session ends this many hours after sign-in, whatever the activity. |
| `LATTICE_COOKIE_SECURE` | unset | Secure flag on cookies. Unset: on in production or when the request is HTTPS. |
| `LATTICE_CHART_COLORS` | `brand` | How charts that name no colour mode are coloured: `brand`, shades of the theme colour, or `neutral`, greys (ADR 0015). |
| `LATTICE_GRID_QUERY_TIMEOUT_SECONDS` | `15` | A grid query (rows, count, export, Ctrl+J results) running longer than this is cancelled, and the user is asked to narrow the search or filters. |
| `LATTICE_BCRYPT_ROUNDS` | `12` | bcrypt cost for password hashes. |
| `LATTICE_PASSWORD_LOGIN_ENABLED` | `true` | Show the email and password form on the sign-in page. |
| `LATTICE_OIDC_ISSUER` | `` | OIDC issuer URL. Set with `oidc_client_id` to show single sign-on. |
| `LATTICE_OIDC_CLIENT_ID` | `` | OIDC client (application) id. |
| `LATTICE_OIDC_CLIENT_SECRET` | `` | OIDC client secret, for confidential clients. |
| `LATTICE_OIDC_REDIRECT_URI` | `http://localhost:8000/auth/oidc/callback` | Callback URL registered with the identity provider. |
| `LATTICE_OIDC_SCOPES` | `openid email profile` | Scopes requested at sign-in. |
| `LATTICE_OIDC_PROVIDER_LABEL` | `Single sign-on` | Text on the sign-in button: Continue with … |
| `LATTICE_OIDC_DEFAULT_ROLE` | `` | Role given to a new user on first SSO sign-in. Empty: no role, and an administrator must grant one. |
| `LATTICE_OIDC_TRUST_EMAIL` | `false` | Link an SSO sign-in to an existing account by email even without `email_verified` in the token. Only for an identity provider whose emails your organisation controls. |
