"""A0 structure test — asserts the repository tree matches docs/31_folder_structure.md.

This is the A0 acceptance check (docs/54, row A0), written at Phase 0 and still live:
drift from the frozen tree fails CI. It verifies presence/shape only — every subsystem's
behavior is asserted by its own suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Subsystem package folders that MUST each ship __init__.py + the four contract docs
# (docs/56). `contracts` is intentionally excluded — it is the shared-types module and
# ships __init__.py only (docs/31).
SUBSYSTEMS = [
    "env",
    "config",
    "ledger",
    "registry",
    "lifecycle",
    "governance",
    "security",
    "router",
    "memory",
    "capabilities",
    "conductor",
    "projections",
    "logging",
]

CONTRACT_DOCS = ["IMPLEMENTATION.md", "API.md", "TESTPLAN.md", "RISKS.md"]

ROOT_FILES = [
    "README.md",
    "AGENTS.md",
    ".gitignore",
    ".env.example",
    "pyproject.toml",
]

PACKAGE_DIRS_WITH_INIT = [
    "charterhouse",
    "charterhouse/contracts",
    "charterhouse/router/adapters",
    "charterhouse/capabilities/framework",
]

TOP_LEVEL_DIRS = [
    "charterhouse",
    "agents",
    "adapters/harness/opencode",
    "config/profiles",
    "vault/inbox",
    "vault/ventures",
    "vault/memory",
    "vault/lessons",
    "vault/playbooks",
    "vault/archive",
    "data/ledger",
    "data/metrics",
    "templates/landing",
    "templates/saas-starter",
    "tests/fixtures",
    "tests/fakes",
    "tests/unit",
    "tests/integration",
    "tests/simulation",
    "tests/invariants",
    "docs",
    "scripts",
]

CONFIG_FILES = [
    "config/providers.yaml",
    "config/models.yaml",
    "config/routes.yaml",
    "config/profiles/free.yaml",
    "config/profiles/cheap-cloud.yaml",
    "config/profiles/local-first.yaml",
]

GENERATED_PLACEHOLDERS = [
    "vault/PIPELINE.md",
    "data/metrics/METRICS.md",
    "docs/BUILD_TRACKER.md",
]


@pytest.mark.parametrize("rel", ROOT_FILES)
def test_root_files_exist(repo_root: Path, rel: str) -> None:
    assert (repo_root / rel).is_file(), f"missing root file: {rel}"


@pytest.mark.parametrize("rel", TOP_LEVEL_DIRS)
def test_top_level_dirs_exist(repo_root: Path, rel: str) -> None:
    assert (repo_root / rel).is_dir(), f"missing directory: {rel}"


@pytest.mark.parametrize("rel", PACKAGE_DIRS_WITH_INIT)
def test_package_dirs_have_init(repo_root: Path, rel: str) -> None:
    assert (repo_root / rel / "__init__.py").is_file(), f"missing __init__.py in {rel}"


@pytest.mark.parametrize("sub", SUBSYSTEMS)
def test_subsystem_has_init(repo_root: Path, sub: str) -> None:
    assert (
        repo_root / "charterhouse" / sub / "__init__.py"
    ).is_file(), f"missing __init__.py in charterhouse/{sub}"


@pytest.mark.parametrize("sub", SUBSYSTEMS)
@pytest.mark.parametrize("doc", CONTRACT_DOCS)
def test_subsystem_has_contract_docs(repo_root: Path, sub: str, doc: str) -> None:
    path = repo_root / "charterhouse" / sub / doc
    assert path.is_file(), f"missing contract doc: charterhouse/{sub}/{doc}"


@pytest.mark.parametrize("rel", CONFIG_FILES + GENERATED_PLACEHOLDERS)
def test_config_and_generated_placeholders_exist(repo_root: Path, rel: str) -> None:
    assert (repo_root / rel).is_file(), f"missing file: {rel}"


def test_contracts_module_has_no_contract_docs(repo_root: Path) -> None:
    """The shared-types module ships __init__.py only, per docs/31."""
    contracts = repo_root / "charterhouse" / "contracts"
    for doc in CONTRACT_DOCS:
        assert not (contracts / doc).exists(), f"contracts/ should not carry {doc}"


def test_gitignore_excludes_pii_and_secrets(repo_root: Path) -> None:
    text = (repo_root / ".gitignore").read_text(encoding="utf-8")
    for pattern in [".env", "*.private.md", "__pycache__", ".venv"]:
        assert pattern in text, f".gitignore must exclude {pattern}"
