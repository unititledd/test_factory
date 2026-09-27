"""Application settings, read from the environment.

Every value has a working local default so `uvicorn app.main:app` runs out
of the box; production overrides come from environment variables.
"""

import os

#: Reservations are fixed at two-hour intervals.
SLOT_DURATION_HOURS = 2

#: Database location. SQLite by default; point at Postgres in production
#: (e.g. postgresql+psycopg://user:pass@host/db).
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./reservations.db")

#: Optional shared secret for the /api/admin/* endpoints. When unset (local
#: development) admin routes are open; when set, requests must send the
#: header `X-Admin-Key: <value>`. See README for production notes.
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY") or None
