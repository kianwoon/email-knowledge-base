import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# +++ Import Base from the single source of truth +++
from app.db.base_class import Base

# --- Model Discovery via Base --- 
# Ensure all your SQLAlchemy models subclass the Base from app.db.base_class
# and are imported somewhere in your application so that Base.metadata is populated.
# Explicit imports here are usually not needed and can cause issues.

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line reads the loggers section in alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
else:
    # Setup default logging if alembic.ini specifies no logging config.
    # You might adjust this based on your application's logging setup.
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('alembic').setLevel(logging.INFO)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# +++ Set target_metadata to your Base.metadata +++
# Models are now imported explicitly above for Alembic's use
target_metadata = Base.metadata
# print(f"DEBUG [env.py]: Metadata Tables Loaded: {list(target_metadata.tables.keys())}") # Can remove debug now
# --- End Set ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
