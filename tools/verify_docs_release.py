"""Reuse verified runtime checks only for an exact, byte-compared documentation release."""

import argparse
import email
import hashlib
import io
import json
import subprocess
import tomllib
import urllib.request
import zipfile

from release_gate import ROOT, version


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "KDPika-SDK-release-check"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def verify_source() -> dict:
    config = json.loads((ROOT / "release-config.json").read_text())["documentation_only"]
    current = str(version())
    assert config["version"] == current and current == "1.1.6"
    assert config["base_version"] == "1.1.5"
    evidence = json.loads(
        get(
            "https://api.github.com/repos/kdpika/kdpika-licensing-python/actions/runs/"
            + str(config["verified_ci_run"])
        )
    )
    assert evidence["conclusion"] == "success" and evidence["status"] == "completed"
    assert evidence["head_sha"] == config["verified_commit"]
    assert evidence["path"] == ".github/workflows/release.yml"
    jobs = json.loads(get(evidence["jobs_url"] + "?per_page=100"))["jobs"]
    checked = [j for j in jobs if j["name"].startswith("verify / ")]
    assert len(checked) == 13 and all(j["conclusion"] == "success" for j in checked)
    base = config["verified_commit"]
    allowed = {
        "README.md",
        "CHANGELOG.md",
        "docs/release.md",
        "pyproject.toml",
        "release-config.json",
        "src/kdpika_licensing/_version.py",
        ".github/workflows/release.yml",
        "tools/verify_docs_release.py",
    }
    changed = set(git("diff", "--name-only", base, "--").decode().splitlines())
    assert changed <= allowed, "Non-documentation files changed: " + str(changed - allowed)
    old = tomllib.loads(git("show", base + ":pyproject.toml").decode())
    new = tomllib.loads((ROOT / "pyproject.toml").read_text())
    expected_urls = {
        **old["project"]["urls"],
        "Source": "https://github.com/kdpika/kdpika-licensing-python",
        "Issues": "https://github.com/kdpika/kdpika-licensing-python/issues",
    }
    assert new["project"]["urls"] == expected_urls
    old["project"]["urls"] = expected_urls
    assert old == new, "Build configuration or dependency constraints changed"
    old_version = git("show", base + ":src/kdpika_licensing/_version.py")
    assert (ROOT / "src/kdpika_licensing/_version.py").read_bytes() == old_version.replace(
        b'"1.1.5"', b'"1.1.6"'
    ), "Version module contains other changes"
    return {"version": current, "reused_ci": evidence["html_url"], "changed_files": sorted(changed)}


def verify_wheel() -> None:
    metadata = json.loads(get("https://pypi.org/pypi/kdpika-licensing/1.1.5/json"))
    old_file = next(f for f in metadata["urls"] if f["filename"].endswith("-py3-none-any.whl"))
    raw = get(old_file["url"])
    assert hashlib.sha256(raw).hexdigest() == old_file["digests"]["sha256"]
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as old,
        zipfile.ZipFile(ROOT / "dist/kdpika_licensing-1.1.6-py3-none-any.whl") as new,
    ):
        code = {n for n in old.namelist() if ".dist-info/" not in n}
        assert code == {n for n in new.namelist() if ".dist-info/" not in n}
        for name in code:
            before = old.read(name)
            if name == "kdpika_licensing/_version.py":
                before = before.replace(b'"1.1.5"', b'"1.1.6"')
            assert before == new.read(name), "Published runtime differs: " + name
        old_prefix = "kdpika_licensing-1.1.5.dist-info/"
        new_prefix = "kdpika_licensing-1.1.6.dist-info/"
        assert old.read(old_prefix + "licenses/LICENSE") == new.read(new_prefix + "licenses/LICENSE")
        before = email.message_from_bytes(old.read(old_prefix + "METADATA"))
        after = email.message_from_bytes(new.read(new_prefix + "METADATA"))
        for key in set(before.keys()) | set(after.keys()):
            if key not in {"Version", "Project-URL"}:
                assert before.get_all(key) == after.get_all(key), "Package metadata changed: " + key
        assert after["Version"] == "1.1.6"
        assert after.get_payload() == (ROOT / "README.md").read_text()
        assert "## Install from the source ZIP" in after.get_payload()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    args = parser.parse_args()
    report = verify_source()
    if args.artifacts:
        verify_wheel()
    print(json.dumps({"result": "PASS", **report, "wheel_compared": args.artifacts}))
