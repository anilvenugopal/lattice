"""Development sign-in accounts. Created by `lattice seed` and listed on the sign-in page
when LATTICE_APP_ENV=development. Never used in production."""

DEV_USERS = [
    # email, display name, password (None = SSO-only), roles
    ("admin@example.com", "Avery Admin", "Admin12345!", ("admin", "editor")),
    ("editor@example.com", "Emery Editor", "Editor12345!", ("editor",)),
    ("viewer@example.com", "Val Viewer", "Viewer12345!", ("viewer",)),
    ("sam.ortiz@example.com", "Sam Ortiz", None, ("editor",)),
    ("priya.nair@example.com", "Priya Nair", None, ("editor",)),
]
