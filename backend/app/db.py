"""Connexion base de données (SQLite en dev, PostgreSQL en production)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.schema import CreateTable

from .config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - simple configuration
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True)


settings.ensure_dirs()
engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (enregistre les tables)

    Base.metadata.create_all(engine)
    _migrate_users()
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Ajoute les colonnes facultatives apparues depuis la création de la base
    (ex. firebase_uid, storage_path), sans toucher aux données existantes."""
    insp = inspect(engine)
    added = False
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                if not column.nullable:
                    raise RuntimeError(f"Colonne obligatoire {table.name}.{column.name} à migrer manuellement.")
                ddl_type = column.type.compile(dialect=engine.dialect)
                conn.exec_driver_sql(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type}")
                added = True
            indexed = {i["name"] for i in insp.get_indexes(table.name)}
            for index in table.indexes:
                if index.name not in indexed and all(c.name not in existing for c in index.columns):
                    index.create(conn)
    if added:
        engine.dispose()


def _migrate_users() -> None:
    """Ajoute nom d'utilisateur + connexion Google aux bases créées avant cette version,
    en conservant tous les comptes existants."""
    from .accounts import suggest_username
    from .models import User

    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    if "username" in columns:
        return
    table = User.__table__
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            # SQLite ne sait pas rendre une colonne facultative : on reconstruit la table.
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            shadow = table.to_metadata(MetaData(), name="users_new")
            shadow.indexes.clear()
            conn.execute(CreateTable(shadow))
            # .keys() est indispensable : itérer sur table.columns donne des objets Column, pas des noms.
            shared = ", ".join(c for c in table.columns.keys() if c in columns)  # noqa: SIM118
            conn.exec_driver_sql(f"INSERT INTO users_new ({shared}) SELECT {shared} FROM users")
            conn.exec_driver_sql("DROP TABLE users")
            conn.exec_driver_sql("ALTER TABLE users_new RENAME TO users")
            for index in table.indexes:
                index.create(conn)
        else:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN username VARCHAR(30), "
                "ADD COLUMN google_sub VARCHAR(64), "
                "ALTER COLUMN email DROP NOT NULL, ALTER COLUMN password_hash DROP NOT NULL"
            )
            for index in table.indexes:
                if index.name in ("ix_users_username", "ix_users_google_sub"):
                    index.create(conn)
        taken: set[str] = set()
        for user_id, email in conn.exec_driver_sql("SELECT id, email FROM users").fetchall():
            name = suggest_username(email or "user", lambda c: c in taken)
            taken.add(name)
            conn.exec_driver_sql("UPDATE users SET username = ? WHERE id = ?" if engine.dialect.name == "sqlite"
                                 else "UPDATE users SET username = %s WHERE id = %s", (name, user_id))
    # Les connexions ouvertes pendant la reconstruction ont les clés étrangères désactivées :
    # on les jette pour que les suivantes réappliquent PRAGMA foreign_keys=ON.
    engine.dispose()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
