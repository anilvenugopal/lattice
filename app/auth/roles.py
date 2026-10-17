"""Built-in role codes. The role table rows are created in alembic/versions/0001."""

ADMIN = "admin"
EDITOR = "editor"
VIEWER = "viewer"

ADMINS = (ADMIN,)
EDITORS = (ADMIN, EDITOR)
