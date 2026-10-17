# Sign-in, roles and sessions

## Methods

Both can be on at once. The login page shows what is configured.

| Method | Setting | Notes |
|---|---|---|
| Password | `PASSWORD_LOGIN_ENABLED=true` | bcrypt (cost `BCRYPT_ROUNDS`, default 12). Policy: 12+ chars, upper, lower, digit (`app/auth/passwords.py`) |
| OIDC | `OIDC_ISSUER`, `OIDC_CLIENT_ID` (+ `OIDC_CLIENT_SECRET` for confidential clients) | Authorization code + PKCE, any provider with `/.well-known/openid-configuration` |

## OIDC setup

1. Register a web application with your provider. Redirect URI:
   `https://<host>/auth/oidc/callback` (dev: `http://localhost:8000/auth/oidc/callback`).
   Post-logout redirect: `https://<host>/auth/login`.
2. Set in `.env`:

```
OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0      # Entra ID
# OIDC_ISSUER=https://<org>.okta.com                                 # Okta
# OIDC_ISSUER=https://<host>/realms/<realm>                          # Keycloak
OIDC_CLIENT_ID=...
OIDC_CLIENT_SECRET=...
OIDC_REDIRECT_URI=https://<host>/auth/oidc/callback
OIDC_PROVIDER_LABEL=Microsoft
OIDC_DEFAULT_ROLE=            # e.g. viewer; empty = new users wait for an admin
OIDC_TRUST_EMAIL=false        # see "Account linking" below
```

3. Restart. Administration › System shows the effective configuration.

First SSO sign-in: the user is matched by `sub`, then by email (the account is
linked), else created. A new user gets `OIDC_DEFAULT_ROLE`, or no role and the
"Access pending" page until an admin grants one.

ID tokens are checked for signature (JWKS), issuer, audience, expiry and nonce.
Only asymmetric signing algorithms are accepted: RS256/384/512, PS256 and ES256/384.

### Account linking

An SSO identity links to an existing account only through the `email` claim,
never through `preferred_username`. It links only when the token has
`email_verified: true`, or when `OIDC_TRUST_EMAIL=true`. Otherwise sign-in is
refused with "Ask an administrator to link your account", so an unverified
email cannot take over a local account.

Entra ID does not send `email_verified`. With Entra you have two choices:

- **Trust the directory.** Set `OIDC_TRUST_EMAIL=true`, but only for a
  single-tenant app whose directory your organisation controls.
- **Start SSO-only.** Create users without a password, so they first sign in
  through SSO and no existing account needs linking.

## Roles

Built-in: `admin` (Administration), `editor` (create/change, bulk actions),
`viewer` (read). Roles gate functions, not rows; scope rows in a grid's `query`.
A user without roles cannot use the app. Admins cannot remove their own admin
role or deactivate themselves.

## Sessions

Server-side rows in `user_session`; the cookie (`lattice_session`, HttpOnly,
SameSite=Lax) carries a random token and the table stores its
SHA-256. Idle timeout `SESSION_IDLE_MINUTES` (480), absolute `SESSION_MAX_HOURS`
(24). Users see and end their sessions under Account › Security; admins under
Administration › Sessions. Password changes, deactivation and password resets
end the user's other sessions.

## Cookie security

All cookies are set through `app/auth/cookies.py`: session, CSRF, the OIDC flow
cookie and flash messages. They carry `Secure` when `COOKIE_SECURE=true`. With the
setting unset, they carry it when `APP_ENV=production` or the request is HTTPS.
Behind a proxy that terminates TLS, run uvicorn with
`--proxy-headers --forwarded-allow-ips=<proxy ip>`, so the app sees the original
scheme.

Password sign-in runs bcrypt even when the email is unknown, so response time
does not reveal which accounts exist.

## CSRF

Double-submit cookie (`lattice_csrf`; the form field is `csrf_token`). HTMX and `app.post()` send `X-CSRF-Token`;
plain forms include `{{ csrf_field() }}`. Every router includes
`Depends(csrf_protect)`.

## First admin in a new environment

```bash
uv run alembic upgrade head
uv run python -m scripts.create_user you@corp.com "Your Name" --role admin
```
