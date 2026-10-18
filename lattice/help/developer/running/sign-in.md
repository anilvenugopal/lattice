---
title: Sign-in and sessions
summary: Configure password and OIDC single sign-on, understand account linking, and how sessions, cookies and CSRF work.
order: 10
keywords: authentication login sso oidc entra azure okta keycloak password session cookie csrf security linking
---

## Sign-in methods

A host can offer password sign-in, single sign-on through OIDC, or both. The
sign-in page shows what is configured.

| Method | Turned on by | Notes |
|---|---|---|
| **Password** | `LATTICE_PASSWORD_LOGIN_ENABLED=true` (the default) | Hashed with bcrypt (cost `LATTICE_BCRYPT_ROUNDS`, default 12). Passwords need 12 or more characters, with an upper-case letter, a lower-case letter and a digit |
| **OIDC** | `LATTICE_OIDC_ISSUER` and `LATTICE_OIDC_CLIENT_ID` (and `LATTICE_OIDC_CLIENT_SECRET` for a confidential client) | Authorization code flow with PKCE. Works with any provider that publishes `/.well-known/openid-configuration` |

Password sign-in runs bcrypt even for an unknown email, so the response time
does not reveal which accounts exist.

## Set up OIDC

1. **Register a web application** with your identity provider:
   - redirect URI: `https://<host>/auth/oidc/callback` (in development,
     `http://localhost:8000/auth/oidc/callback`);
   - post-logout redirect: `https://<host>/auth/login`.
2. **Set the settings**, in the environment or `.env`:

   ```bash
   LATTICE_OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0   # Entra ID
   # LATTICE_OIDC_ISSUER=https://<org>.okta.com                              # Okta
   # LATTICE_OIDC_ISSUER=https://<host>/realms/<realm>                       # Keycloak
   LATTICE_OIDC_CLIENT_ID=…
   LATTICE_OIDC_CLIENT_SECRET=…
   LATTICE_OIDC_REDIRECT_URI=https://<host>/auth/oidc/callback
   LATTICE_OIDC_PROVIDER_LABEL=Microsoft          # the button reads "Continue with Microsoft"
   LATTICE_OIDC_DEFAULT_ROLE=                     # e.g. viewer; empty = new users wait for an admin
   LATTICE_OIDC_TRUST_EMAIL=false                 # see Account linking
   ```

3. **Restart the host.** **Administration › System** shows the sign-in
   configuration in effect.

On a user's first SSO sign-in, Lattice looks for an account in this order:

1. one already linked to the token's `sub`;
2. one with the token's email, which is then linked (see below);
3. otherwise it creates a new account.

A new account takes its email from the `email` claim, or from
`preferred_username` when the token has no `email`. It gets
`LATTICE_OIDC_DEFAULT_ROLE`. With no default role, the
user sees an "Access pending" page until an administrator grants one.

**Token checks.** ID tokens are checked for:

- the signature, against the provider's published keys;
- the issuer, audience and expiry;
- the nonce.

Only asymmetric signing algorithms are accepted: RS256, RS384, RS512, PS256,
ES256 and ES384.

### Account linking

An SSO identity links to an existing account only through the `email` claim,
never through `preferred_username`. It links only when:

- the token has `email_verified: true`, or
- `LATTICE_OIDC_TRUST_EMAIL=true`.

Otherwise sign-in is refused with "Ask an administrator to link your account".
This stops someone with an unverified email from taking over a local account.

Entra ID does not send `email_verified`. With Entra you have two choices:

- **Trust the directory.** Set `LATTICE_OIDC_TRUST_EMAIL=true`, but only for a
  single-tenant app whose directory your organisation controls.
- **Start SSO-only.** Create users without a password
  (`lattice create-user … --no-password`), so their first sign-in is through
  SSO and no existing account needs linking.

## Sessions

Sessions are rows in the `user_session` table:

- **The cookie.** `lattice_session` holds a random token. It is HttpOnly and
  SameSite=Lax.
- **The table.** It stores only the SHA-256 hash of the token, so a copy of
  the database cannot be used to sign in.
- **Idle timeout.** A session ends after `LATTICE_SESSION_IDLE_MINUTES`
  without a request (default 480).
- **Absolute limit.** A session also ends `LATTICE_SESSION_MAX_HOURS` after
  sign-in, whatever the activity (default 24).

Who can end sessions:

- **Users** see and end their own sessions in **Account › Security**.
- **Administrators** see and revoke every session in
  **Administration › Sessions**.
- **Automatically.** Changing a password, deactivating a user and resetting a
  password end that user's other sessions.

## Cookies

Every cookie is set in one place, `lattice/kernel/auth/cookies.py`:

- the session;
- CSRF;
- the OIDC flow (a signed, ten-minute cookie holding the state, nonce and PKCE verifier);
- flash messages.

Cookies carry `Secure` when `LATTICE_COOKIE_SECURE=true`. With the setting
unset, they carry it in production or when the request is HTTPS.

Behind a proxy that terminates TLS, run uvicorn with
`--proxy-headers --forwarded-allow-ips=<proxy address>`, so Lattice sees the
original scheme.

## CSRF

Lattice uses a double-submit cookie. The `lattice_csrf` cookie must match
either the `csrf_token` form field or the `X-CSRF-Token` header:

- **Forms** include `{{ csrf_field() }}`.
- **HTMX and `app.post()`** send the header automatically.
- **Routers** that change data declare `Depends(csrf_protect)`.

See [Forms and feedback](../building-apps/forms-and-feedback.md#csrf).
