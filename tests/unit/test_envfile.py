"""load_env_file (charterhouse/env/envfile.py) — the A1 .env loader.

All values are short fakes (never real keys; < 12 chars so the secret-scan gate stays
quiet). ``os.environ`` is snapshot/restored around every test so nothing leaks between
tests or into the rest of the suite (which stays on FakeProvider — no real keys anywhere).
"""

from __future__ import annotations

import os

import pytest

from charterhouse.env import load_env_file


@pytest.fixture()
def clean_env():
    before = dict(os.environ)
    yield
    for k in list(os.environ):
        if k not in before:
            del os.environ[k]
    for k, v in before.items():
        os.environ[k] = v


def _write(path, text):  # noqa: ANN001
    path.write_text(text, encoding="utf-8")
    return path


def test_parses_windows_backslash_path_without_mangling(tmp_path, clean_env):
    """The whole reason for a real parser over ``bash source``: a backslashed Windows path
    survives byte-for-byte (sourcing would eat the backslashes)."""
    env = _write(tmp_path / ".env",
                 "CHARTERHOUSE_ROOT=K:\\the_charter_house\r\nFAKE_PROVIDER_KEY=xyz789\r\n")
    load_env_file(env)
    assert os.environ["CHARTERHOUSE_ROOT"] == "K:\\the_charter_house"
    assert os.environ["FAKE_PROVIDER_KEY"] == "xyz789"


def test_returns_names_only_never_values(tmp_path, clean_env):
    env = _write(tmp_path / ".env", "FAKE_PROVIDER_KEY=xyz789\nOTHER_FAKE=abc123\n")
    names = load_env_file(env)
    assert names == ("FAKE_PROVIDER_KEY", "OTHER_FAKE")  # sorted names
    assert "xyz789" not in names and "abc123" not in names


def test_missing_file_is_a_noop(tmp_path, clean_env):
    assert load_env_file(tmp_path / "nope.env") == ()


def test_existing_var_wins_unless_override(tmp_path, clean_env):
    os.environ["SHARED_FAKE"] = "real"
    env = _write(tmp_path / ".env", "SHARED_FAKE=fromfile\n")
    load_env_file(env)
    assert os.environ["SHARED_FAKE"] == "real"  # a real env var beats the file
    load_env_file(env, override=True)
    assert os.environ["SHARED_FAKE"] == "fromfile"


def test_never_prints_a_value(tmp_path, clean_env, capsys):
    env = _write(tmp_path / ".env", "FAKE_PROVIDER_KEY=xyz789\n")
    load_env_file(env)
    out = capsys.readouterr()
    assert out.out == "" and "xyz789" not in out.err
