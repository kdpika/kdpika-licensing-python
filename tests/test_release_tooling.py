"""Owner/repository/tag/license gates and workflow restrictions; never publish."""

import hashlib
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def test_release_text_attributes_preserve_license_bytes():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in attributes.splitlines()
    assert "include .gitattributes" in (ROOT / "MANIFEST.in").read_text(encoding="utf-8")


@pytest.fixture
def gate(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    module = importlib.import_module("release_gate")
    source = tmp_path / "src/kdpika_licensing"
    source.mkdir(parents=True)
    (source / "_version.py").write_text('__version__ = "1.1.0rc1"\n')
    legal = b"SYNTHETIC TEST TERMS ONLY, NOT THE PROJECT LICENSE"
    (tmp_path / "LICENSE").write_bytes(legal)
    config = {
        "package": "kdpika-licensing",
        "name_approved": True,
        "version_approved": True,
        "license_approved": True,
        "approved_license_sha256": hashlib.sha256(legal).hexdigest(),
        "support_email": "support@example.invalid",
        "support_email_approved": True,
        "repository": "synthetic-owner/synthetic-sdk",
    }
    return module, config, tmp_path


def test_synthetic_prerelease_gate(gate):
    module, config, root = gate
    assert module.validate(config, "v1.1.0rc1", config["repository"], root).is_prerelease


def test_synthetic_stable_gate(gate):
    module, config, root = gate
    (root / "src/kdpika_licensing/_version.py").write_text('__version__ = "1.1.0"\n')
    assert not module.validate(config, "v1.1.0", config["repository"], root).is_prerelease


@pytest.mark.parametrize(
    "field", ["name_approved", "version_approved", "license_approved", "support_email_approved"]
)
def test_unapproved_owner_decision_blocks(gate, field):
    module, config, root = gate
    config[field] = False
    with pytest.raises(ValueError):
        module.validate(config, "v1.1.0rc1", config["repository"], root)


@pytest.mark.parametrize(
    "patch",
    [
        {"package": "another-package"},
        {"repository": "TODO(owner decision)"},
        {"support_email": ""},
        {"approved_license_sha256": "unapproved"},
    ],
)
def test_mismatched_identity_or_license_blocks(gate, patch):
    module, config, root = gate
    config.update(patch)
    with pytest.raises(ValueError):
        module.validate(config, "v1.1.0rc1", "synthetic-owner/synthetic-sdk", root)


@pytest.mark.parametrize(
    "tag,repository", [("v1.1.0", "synthetic-owner/synthetic-sdk"), ("v1.1.0rc1", "another/repository")]
)
def test_wrong_tag_or_repository_blocks(gate, tag, repository):
    module, config, root = gate
    with pytest.raises(ValueError):
        module.validate(config, tag, repository, root)


def test_checked_in_real_gate_obeys_owner_configuration(gate):
    module, _, _ = gate
    config = json.loads((ROOT / "release-config.json").read_text(encoding="utf-8"))
    if all(
        config.get(k) is True
        for k in ["name_approved", "version_approved", "license_approved", "support_email_approved"]
    ):
        module.validate(config, "v" + str(module.version()), config["repository"])
    else:
        with pytest.raises(ValueError):
            module.validate(config, "v" + str(module.version()), config["repository"])


def test_information_only_notice_cannot_be_approved(gate):
    module, config, root = gate
    original = b"SDK license information\n\nThis file documents the existing source package's licensing metadata. It does\nnot create an open-source license or grant additional rights. The existing\nPython/PHP/JavaScript metadata identifies proprietary licensing; the C# project\ndoes not declare a separate package license. Use and redistribution are governed\nby the applicable agreement with KDPika. Contact hi@kdpika.com for the terms\nthat apply to your integration or redistribution. No public registry release,\npublic repository or general redistribution grant is asserted by this file.\n"
    (root / "LICENSE").write_bytes(original)
    config["approved_license_sha256"] = hashlib.sha256(original).hexdigest()
    with pytest.raises(ValueError):
        module.validate(config, "v1.1.0rc1", config["repository"], root)


def test_approved_sdk_license_matches_metadata_and_hash():
    import tomllib

    config = json.loads((ROOT / "release-config.json").read_text(encoding="utf-8"))
    license_bytes = (ROOT / "LICENSE").read_bytes()
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert license_bytes.startswith(b"MIT License\n")
    assert metadata["project"]["license"] == "MIT"
    assert config["license_approved"] is True
    assert config["approved_license_sha256"] == hashlib.sha256(license_bytes).hexdigest()


def test_workflow_action_pins_and_publish_isolation():
    import re

    workflows = ROOT / ".github/workflows"
    for file in workflows.glob("*.yml"):
        content = file.read_text(encoding="utf-8")
        for action in re.findall(r"uses: ([^\s#]+)", content):
            if not action.startswith("./"):
                assert re.fullmatch(r"[A-Za-z0-9_./-]+@[0-9a-f]{40}", action)
        assert "secrets.PYPI" not in content
        assert "pull_request_target" not in content
    release = (workflows / "release.yml").read_text(encoding="utf-8")
    assert release.count("id-token: write") == 2
    assert "environment: testpypi" in release and "environment: pypi" in release
    assert "needs: [prepare, verify, verify_documentation]" in release


def test_native_matrix_keeps_all_python_versions_and_native_macos_build():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "os: [ubuntu-latest, macos-15-intel, windows-latest]" in ci
    assert "brew install openssl@3" in ci
    assert 'echo "OPENSSL_DIR=$(brew --prefix openssl@3)"' in ci
    assert 'python: ["3.11", "3.12", "3.13", "3.14"]' in ci
    assert "python -m pytest --cov" in ci
