"""Verify the exact documentation-only 2.0.2 release against verified 2.0.1 bytes."""
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


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'KDPika-documentation-release'})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()


def verify_source():
    config = json.loads((ROOT / 'release-config.json').read_text())['documentation_only']
    assert str(version()) == config['version'] == '2.0.2'
    assert config['base_version'] == '2.0.1'
    base = config['verified_commit']
    assert base == 'a5559f901aa2cd2e6b2977c3f8e74ab45818e4eb'
    run = json.loads(get('https://api.github.com/repos/kdpika/kdpika-licensing-python/actions/runs/' + str(config['verified_ci_run'])))
    assert run['status'] == 'completed' and run['conclusion'] == 'success'
    assert run['head_sha'] == base and run['path'] == '.github/workflows/release.yml'
    allowed = {'README.md', 'CHANGELOG.md', 'MANIFEST.in', 'docs/upgrading.md', 'release-config.json',
               'src/kdpika_licensing/_version.py', 'tools/verify_docs_release.py'}
    changes = set(git('diff', '--name-only', base, '--').decode().splitlines())
    assert all(name in allowed or name.startswith('examples/python-projects/') for name in changes), changes
    assert (ROOT / 'pyproject.toml').read_bytes() == git('show', base + ':pyproject.toml')
    tracked = git('ls-tree', '-r', '--name-only', base, 'src').decode().splitlines()
    for name in tracked:
        expected = git('show', base + ':' + name)
        if name == 'src/kdpika_licensing/_version.py':
            expected = expected.replace(b'"2.0.1"', b'"2.0.2"')
        assert (ROOT / name).read_bytes() == expected, 'Runtime changed: ' + name
    assert set(git('ls-files', 'src').decode().splitlines()) == set(tracked)
    return {'version': '2.0.2', 'runtime_byte_comparison': 'PASS', 'reused_ci': run['html_url'], 'changed_files': sorted(changes)}


def verify_wheel():
    data = json.loads(get('https://pypi.org/pypi/kdpika-licensing/2.0.1/json'))
    release = next(f for f in data['urls'] if f['filename'].endswith('-py3-none-any.whl'))
    raw = get(release['url'])
    assert hashlib.sha256(raw).hexdigest() == release['digests']['sha256']
    with zipfile.ZipFile(io.BytesIO(raw)) as before, zipfile.ZipFile(ROOT / 'dist/kdpika_licensing-2.0.2-py3-none-any.whl') as after:
        code = {n for n in before.namelist() if '.dist-info/' not in n}
        assert code == {n for n in after.namelist() if '.dist-info/' not in n}
        for name in code:
            expected = before.read(name)
            if name == 'kdpika_licensing/_version.py':
                expected = expected.replace(b'"2.0.1"', b'"2.0.2"')
            assert after.read(name) == expected, 'Published runtime changed: ' + name
        old_prefix, new_prefix = 'kdpika_licensing-2.0.1.dist-info/', 'kdpika_licensing-2.0.2.dist-info/'
        old = email.message_from_bytes(before.read(old_prefix + 'METADATA'))
        new = email.message_from_bytes(after.read(new_prefix + 'METADATA'))
        for key in set(old.keys()) | set(new.keys()):
            if key != 'Version':
                assert old.get_all(key) == new.get_all(key), 'Dependency/metadata changed: ' + key
        assert after.read(new_prefix + 'licenses/LICENSE') == before.read(old_prefix + 'licenses/LICENSE')
        description = after.read(new_prefix + 'METADATA').split(b'\n\n', 1)[1].decode()
        assert description.rstrip() == (ROOT / 'README.md').read_text().rstrip()
        for phrase in ['## Update, reinstall or remove the SDK', '## Easiest route: open the desktop demo', 'Python 3.9', 'Start Demo.command']:
            assert phrase in description


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', action='store_true')
    args = parser.parse_args()
    result = verify_source()
    if args.artifacts:
        verify_wheel()
    print(json.dumps({'result': 'PASS', **result, 'wheel_compared': args.artifacts}))
