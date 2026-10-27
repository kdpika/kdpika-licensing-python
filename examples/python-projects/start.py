"""Safe entry point: locate supported Python and use this demo's private environment.

This launcher deliberately parses on Python 3.9 so it can explain/avoid the macOS
system-Python problem before importing the SDK. It never changes global packages.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ENV = ROOT / '.demo-venv'
SDK_VERSION = '2.0.1'
SUPPORTED = ((3, 11), (3, 15))


def probe(command):
    try:
        result = subprocess.run(command + ['-c', 'import sys,json; print(json.dumps([list(sys.version_info[:2]),sys.executable]))'],
                                capture_output=True, text=True, timeout=15)
        version, executable = json.loads(result.stdout)
        if result.returncode == 0 and SUPPORTED[0] <= tuple(version) < SUPPORTED[1]:
            return executable
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def choose_python():
    candidates = [[sys.executable]]
    for minor in (14, 13, 12, 11):
        candidates.extend([[str(Path('/Library/Frameworks/Python.framework/Versions') / ('3.' + str(minor)) / 'bin' / ('python3.' + str(minor)))],
                           ['python3.' + str(minor)]])
        if os.name == 'nt':
            candidates.append(['py', '-3.' + str(minor)])
    candidates.extend([['python3'], ['python']])
    for command in candidates:
        executable = probe(command)
        if executable:
            return executable
    raise RuntimeError('Python 3.11–3.14 is needed. Install Python 3.14 from https://www.python.org/downloads/, then start this demo again. Python 3.9 cannot run this SDK.')


def environment_python():
    return ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def checked(command):
    result = subprocess.run([str(item) for item in command], cwd=ROOT)
    if result.returncode:
        raise RuntimeError('Setup did not finish. Read the message above. Check your internet connection and supported Python installation, then start again. Your global Python packages were not changed.')


def main():
    parser = argparse.ArgumentParser(description='Prepare and open the KDPika desktop demo without editing code.')
    parser.add_argument('--setup-only', action='store_true', help='Install/check this demo environment without opening a window')
    parser.add_argument('--update', action='store_true', help='Install the demo-tested SDK version in this demo environment')
    parser.add_argument('--check', action='store_true', help='Show the selected Python and SDK, without installing or opening a window')
    parser.add_argument('--uninstall', action='store_true', help='Remove the SDK from this demo environment only; does not deactivate machines')
    args = parser.parse_args()
    local = environment_python()
    if ENV.is_symlink():
        raise RuntimeError('The demo environment cannot be a linked folder. Extract a fresh copy of the ZIP into a private folder.')
    if args.uninstall:
        if not local.exists():
            print('No demo environment exists. Nothing was removed.')
            return 0
        if not (ENV / 'pyvenv.cfg').is_file():
            raise RuntimeError('This folder is not a Python virtual environment. Nothing was removed.')
        print('This removes only the SDK from .demo-venv. It does not release a machine or remove saved license state.')
        checked([local, '-m', 'pip', 'uninstall', 'kdpika-licensing'])
        return 0
    python = probe([str(local)]) if local.exists() else None
    if local.exists() and python is None:
        raise RuntimeError('The existing demo environment uses an unsupported Python. Remove only the generated .demo-venv folder, then start again. Your saved license state is outside that folder.')
    python = python or choose_python()
    print('Python selected: ' + python, flush=True)
    if args.check:
        code = 'import importlib.metadata as m; print("SDK:",m.version("kdpika-licensing"))'
        if local.exists():
            return subprocess.run([str(local), '-c', code]).returncode
        print('Demo environment not created yet. Start normally to prepare it.')
        return 0
    tk = subprocess.run([python, '-c', 'import tkinter'], capture_output=True)
    if tk.returncode:
        raise RuntimeError('This Python installation has no Tkinter window support. On macOS/Windows use Python 3.14 from python.org. On Debian/Ubuntu install the Tk package matching this Python (often python3-tk). Start again afterwards.')
    if not local.exists():
        if ENV.exists():
            raise RuntimeError('An incomplete .demo-venv folder exists. Remove only that generated folder, then start again. Keep your .kdpika-python-tutorial state folder.')
        print('Step 1/2 · Preparing a separate environment for this demo…', flush=True)
        checked([python, '-m', 'venv', ENV])
    code = 'import importlib.metadata as m; assert m.version("kdpika-licensing")=="' + SDK_VERSION + '"'
    installed = subprocess.run([str(local), '-c', code], capture_output=True).returncode == 0
    if args.update or not installed:
        print('Step 2/2 · Installing the tested SDK ' + SDK_VERSION + ' into the demo environment…', flush=True)
        checked([local, '-m', 'pip', '--isolated', 'install', '--index-url', 'https://pypi.org/simple',
                 '--upgrade', 'kdpika-licensing==' + SDK_VERSION])
    print('Ready · SDK ' + SDK_VERSION + '. App ID and Test/Live are entered inside the window.', flush=True)
    if args.setup_only:
        return 0
    return subprocess.run([str(local), str(ROOT / 'desktop.py')], cwd=ROOT).returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as error:
        print('\nCould not start: ' + str(error), file=sys.stderr)
        print('Help: https://licensing.kdpika.com/docs/v1/tutorials/python/desktop', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nSetup stopped. Start again when ready.')
        sys.exit(130)
