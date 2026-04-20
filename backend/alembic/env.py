from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.db.models import Base
from backend.db.url import build_postgres_url_string


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow db_url override via alembic -x db_url=... to bypass ConfigParser %
# interpolation that corrupts passwords containing % (e.g. ! in SmartTutor2025!SecurePass)
_db_url = config.get_main_option("db_url")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)
else:
    config.set_main_option("sqlalchemy.url", build_postgres_url_string())
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
