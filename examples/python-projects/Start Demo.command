#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  python3 start.py "$@"
elif [ -x /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 ]; then
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 start.py "$@"
else
  echo 'Install Python 3.14 from https://www.python.org/downloads/ and start again.'
  exit 1
fi
