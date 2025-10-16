import os
import sys


def detect_environment() -> str:
    if "pytest" in sys.argv[0] or "pytest" in " ".join(sys.argv):
        return "testing"

    env = os.getenv("ENVIRONMENT")
    if env:
        return env.lower()

    return "development"


environment = detect_environment()

if environment == "testing":
    from database.session_sqlite import (
        get_sqlite_db as get_db,
        reset_sqlite_database as reset_database,
    )
else:
    from database.session_postgresql import (
        get_postgresql_db as get_db,
        reset_postgresql_database as reset_database,
    )

print(f"[database] Using environment: {environment}")


from database.models.accounts import UserModel # noqa
from database.models.movies import Movie # noqa
