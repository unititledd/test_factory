"""Application settings, read from the environment (and a local .env file).

Every value has a working local default so `uvicorn app.main:app` runs out
of the box; overrides come from a git-ignored `.env` file or environment
variables.
"""

import os

from dotenv import load_dotenv

# A local .env file (git-ignored) overrides the SQLite default, e.g.
# DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/reservations_dev
load_dotenv()

#: Reservations are fixed at two-hour intervals.
SLOT_DURATION_HOURS = 2

#: Database location. Falls back to a local SQLite file (quickstart/CI);
#: point at a server database such as Postgres via .env or the environment.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./reservations.db")

#: Optional shared secret for the /api/admin/* endpoints. When unset (local
#: development) admin routes are open; when set, requests must send the
#: header `X-Admin-Key: <value>`. See README for production notes.
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY") or None
