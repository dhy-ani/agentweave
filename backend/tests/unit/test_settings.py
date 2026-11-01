import logging
import os

import pytest

import settings


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
