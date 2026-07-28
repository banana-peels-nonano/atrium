"""env_key_lookup (charterhouse/env/keys.py) — the A1 secret seam for the transport.

Injected env mapping everywhere (no real os.environ, no real secret): the seam returns a
value by NAME, refuses a missing/empty var naming only the variable, and never leaks the
value into the error. Short fake values (< 12 chars) keep the secret-scan gate quiet.
"""

from __future__ import annotations

import pytest

from charterhouse.env import env_key_lookup
from charterhouse.env.types import MissingEnvVar

FAKE = "abc12345"  # < 12 chars; not a real key format


def test_returns_value_for_present_var():
    lookup = env_key_lookup({"GROQ_API_KEY": FAKE})
    assert lookup("GROQ_API_KEY") == FAKE


def test_missing_var_refuses_naming_only_the_name():
    lookup = env_key_lookup({})
    with pytest.raises(MissingEnvVar) as exc:
        lookup("GEMINI_API_KEY")
    assert "GEMINI_API_KEY" in str(exc.value)


def test_empty_var_is_refused_like_missing():
    lookup = env_key_lookup({"GROQ_API_KEY": ""})
    with pytest.raises(MissingEnvVar):
        lookup("GROQ_API_KEY")


def test_error_never_contains_the_value(capsys):
    """A wrong-name lookup names the missing var; the lookup emits no output (no logging of
    any secret). A present secret is returned, never printed."""
    lookup = env_key_lookup({"GROQ_API_KEY": FAKE})
    with pytest.raises(MissingEnvVar) as exc:
        lookup("MISSING_ONE")
    assert FAKE not in str(exc.value)
    lookup("GROQ_API_KEY")
    assert capsys.readouterr().out == ""


def test_two_names_are_independent():
    lookup = env_key_lookup({"GROQ_API_KEY": "grq99999", "GEMINI_API_KEY": "gmi88888"})
    assert lookup("GROQ_API_KEY") == "grq99999"
    assert lookup("GEMINI_API_KEY") == "gmi88888"
