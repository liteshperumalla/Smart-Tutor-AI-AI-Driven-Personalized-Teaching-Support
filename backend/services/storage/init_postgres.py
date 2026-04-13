"""Apply Alembic migrations to initialize the PostgreSQL schema."""

from pathlib import Path

import psycopg2
from alembic import command
from alembic.config import Config

from backend.config import config
from backend.db.url import build_postgres_url_string
from backend.logger import get_logger

logger = get_logger(__name__)


def init_postgres_schema():
    """Apply the Alembic migration head to PostgreSQL and verify the result."""

    print("=" * 70)
    print("Applying PostgreSQL Alembic Migrations")
    print("=" * 70)
    print()

    # Connection parameters
    conn_params = {
        'host': config.POSTGRES_HOST,
        'port': config.POSTGRES_PORT,
        'database': config.POSTGRES_DB,
        'user': config.POSTGRES_USER,
        'password': config.POSTGRES_PASSWORD
    }

    print(f"Connecting to PostgreSQL:")
    print(f"  Host: {conn_params['host']}")
    print(f"  Database: {conn_params['database']}")
    print(f"  User: {conn_params['user']}")
    print()

    try:
        repo_root = Path(__file__).resolve().parents[3]
        alembic_ini = repo_root / "alembic.ini"
        if not alembic_ini.exists():
            raise FileNotFoundError(f"Missing Alembic configuration: {alembic_ini}")

        alembic_cfg = Config(str(alembic_ini))
        # alembic.ini already sets script_location = backend/alembic and
        # prepends backend/ to sys.path — only override the DB URL here.
        alembic_cfg.set_main_option("sqlalchemy.url", build_postgres_url_string())

        print("Running Alembic upgrade head...")
        command.upgrade(alembic_cfg, "head")
        print("✅ Alembic migrations applied")
        print()

        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()

        print("✅ Connected to PostgreSQL")
        print()

        # Verify tables
        print("Verifying tables...")
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cur.fetchall()

        print("✅ Tables in database:")
        for table in tables:
            print(f"  • {table[0]}")
        print()

        # Close connection
        cur.close()
        conn.close()

        print("=" * 70)
        print("✅ PostgreSQL Schema Initialized Successfully!")
        print("=" * 70)
        print()
        print("Schema is now managed by Alembic migrations")

        return True

    except Exception as e:
        print(f"❌ Error initializing schema: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    init_postgres_schema()
