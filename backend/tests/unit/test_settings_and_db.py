import logging
import os

import pytest
from sqlalchemy import create_engine, inspect, text

import settings
from db import database
from db.database import normalize_database_url
from db.models import PLACEHOLDER_EMAIL_DOMAIN, placeholder_email
from db.schema import init_schema


# -- settings.cors_origins ---------------------------------------------------------

def test_cors_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert settings.cors_origins() == [
        "http://localhost:3000", "http://localhost:3100", "https://dhy-ani.github.io",
    ]


@pytest.mark.parametrize("raw", ["", " , ,", ","])
def test_cors_defaults_when_only_blank_entries(monkeypatch, raw):
    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert settings.cors_origins() == list(settings.DEFAULT_CORS_ORIGINS)


def test_cors_parses_comma_list_trimming_whitespace_and_trailing_slash(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://a.example/ ,http://localhost:3000,, https://b.example ")
    assert settings.cors_origins() == ["https://a.example", "http://localhost:3000", "https://b.example"]


def test_cors_default_list_is_a_fresh_copy(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings.cors_origins().append("https://evil.example")
    assert "https://evil.example" not in settings.cors_origins()


# -- settings._load_dotenv -----------------------------------------------------------

def test_load_dotenv_sets_missing_variables_only(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment line\n"
        "\n"
        "AW_TEST_PLAIN = value one \n"
        "AW_TEST_DQ=\"quoted\"\n"
        "AW_TEST_SQ='single'\n"
        "AW_TEST_URL=postgres://u:p@h/db?x=1\n"
        "NOT_AN_ASSIGNMENT\n"
        "#AW_TEST_COMMENTED=1\n"
        "AW_TEST_EXISTING=from-file\n",
        encoding="utf-8",
    )
    for key in ("AW_TEST_PLAIN", "AW_TEST_DQ", "AW_TEST_SQ", "AW_TEST_URL", "AW_TEST_COMMENTED"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AW_TEST_EXISTING", "from-env")
    settings._load_dotenv(str(env_file))
    assert os.environ["AW_TEST_PLAIN"] == "value one"
    assert os.environ["AW_TEST_DQ"] == "quoted"
    assert os.environ["AW_TEST_SQ"] == "single"
    assert os.environ["AW_TEST_URL"] == "postgres://u:p@h/db?x=1"
    assert "AW_TEST_COMMENTED" not in os.environ
    assert "NOT_AN_ASSIGNMENT" not in os.environ
    assert os.environ["AW_TEST_EXISTING"] == "from-env"
    for key in ("AW_TEST_PLAIN", "AW_TEST_DQ", "AW_TEST_SQ", "AW_TEST_URL"):
        monkeypatch.delenv(key)


def test_load_dotenv_ignores_missing_file(tmp_path):
    settings._load_dotenv(str(tmp_path / "absent.env"))


def test_configure_logging_uses_uppercased_level(monkeypatch):
    captured = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: captured.update(kw))
    monkeypatch.setenv("LOG_LEVEL", "debug")
    settings.configure_logging()
    assert captured["level"] == "DEBUG"
    assert "%(levelname)s" in captured["format"]
    monkeypatch.delenv("LOG_LEVEL")
    settings.configure_logging()
    assert captured["level"] == "INFO"


# -- db.database ---------------------------------------------------------------------

@pytest.mark.parametrize("url, expected", [
    ("postgres://u:p@host:5432/db?sslmode=require", "postgresql+psycopg://u:p@host:5432/db?sslmode=require"),
    ("postgresql://u@host/db", "postgresql+psycopg://u@host/db"),
    ("postgresql+psycopg://u@host/db", "postgresql+psycopg://u@host/db"),
    ("sqlite:///./x.db", "sqlite:///./x.db"),
    ("mysql://u@h/db", "mysql://u@h/db"),
    ("my-postgres://u@h/db", "my-postgres://u@h/db"),
])
def test_normalize_database_url(url, expected):
    assert normalize_database_url(url) == expected


def test_default_url_is_backend_sqlite_locally(monkeypatch):
    monkeypatch.setenv("VERCEL", "")
    url = database._default_url()
    assert url == f"sqlite:///{os.path.join(database.BACKEND_DIR, 'agentweave.db')}"


def test_default_url_on_vercel_is_tmp_sqlite_with_warning(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(database.tempfile, "gettempdir", lambda: str(tmp_path))
    with caplog.at_level(logging.WARNING, logger="db.database"):
        url = database._default_url()
    assert url == f"sqlite:///{os.path.join(str(tmp_path), 'agentweave.db')}"
    assert "DATABASE_URL is not set" in caplog.text


def test_engine_uses_session_database_url():
    assert database.DATABASE_URL == os.environ["DATABASE_URL"]
    assert database.engine.dialect.name == "sqlite"


def test_get_db_yields_session_and_closes_it(monkeypatch):
    events = []

    class FakeSession:
        def close(self):
            events.append("closed")

    monkeypatch.setattr(database, "SessionLocal", FakeSession)
    gen = database.get_db()
    session = next(gen)
    assert isinstance(session, FakeSession) and events == []
    with pytest.raises(StopIteration):
        next(gen)
    assert events == ["closed"]


def test_get_db_closes_session_when_request_fails(monkeypatch):
    events = []
    monkeypatch.setattr(database, "SessionLocal", lambda: type("S", (), {"close": lambda s: events.append(1)})())
    gen = database.get_db()
    next(gen)
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("boom"))
    assert events == [1]


# -- db.models / db.schema ------------------------------------------------------------

def test_placeholder_email_uses_reserved_domain():
    assert placeholder_email("uid42") == "uid42@users.agentweave.invalid"
    assert PLACEHOLDER_EMAIL_DOMAIN.endswith(".invalid")


def test_init_schema_creates_all_tables(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'a.db').as_posix()}")
    init_schema(engine)
    assert set(inspect(engine).get_table_names()) == {
        "users", "saved_outfits", "wardrobe_items", "style_preferences", "shopping_clicks",
    }
    engine.dispose()


def test_init_schema_adds_new_nullable_columns_to_existing_tables(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:
        # wardrobe_items as created before image_url / clip_embedding existed
        conn.execute(text(
            "CREATE TABLE wardrobe_items (id INTEGER PRIMARY KEY, user_id INTEGER, item_uuid VARCHAR(36), "
            "filename VARCHAR(255), category VARCHAR(32), color VARCHAR(64), description TEXT, "
            "clip_vector TEXT, added_at DATETIME)"
        ))
    init_schema(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("wardrobe_items")}
    assert {"image_url", "clip_embedding"} <= cols
    init_schema(engine)  # idempotent
    engine.dispose()


def test_init_schema_refuses_to_add_not_null_columns(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE shopping_clicks (id INTEGER PRIMARY KEY, user_id INTEGER)"))
    with pytest.raises(RuntimeError, match="Cannot auto-add NOT NULL column shopping_clicks"):
        init_schema(engine)
    engine.dispose()


# -- tests added from mutation-testing survivors --------------------------------------

def test_load_dotenv_skips_commented_assignments_and_keeps_inner_letters(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("#AW_TEST_HASHED=1\nAW_TEST_LETTERS=\"XRAYX\"\nAW_TEST_SQ_LETTERS='XAX'\n",
                        encoding="utf-8")
    for key in ("#AW_TEST_HASHED", "AW_TEST_LETTERS", "AW_TEST_SQ_LETTERS"):
        monkeypatch.delenv(key, raising=False)
    settings._load_dotenv(str(env_file))
    assert "#AW_TEST_HASHED" not in os.environ
    assert os.environ["AW_TEST_LETTERS"] == "XRAYX"
    assert os.environ["AW_TEST_SQ_LETTERS"] == "XAX"
    monkeypatch.delenv("AW_TEST_LETTERS")
    monkeypatch.delenv("AW_TEST_SQ_LETTERS")


def test_cors_only_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://APPX/,https://x.example")
    assert settings.cors_origins() == ["https://APPX", "https://x.example"]


def test_configure_logging_format(monkeypatch):
    captured = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: captured.update(kw))
    settings.configure_logging()
    assert captured["format"] == "%(asctime)s %(levelname)s %(name)s: %(message)s"
