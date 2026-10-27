# KDPika Python demo · project 1.1.0

Real licensing, not a simulated success. Tested SDK: **2.0.1**. Desktop setup no longer needs source edits or environment variables.

## Install Python once

Use **Python 3.14** from [python.org](https://www.python.org/downloads/) for the easiest new setup. The SDK supports **3.11–3.14**. Installing Python and installing the SDK are different steps. The old Python 3.9 supplied by macOS developer tools cannot run the current SDK.

- **Windows:** install Python 3.14 with its Python launcher. Open **PowerShell** from the Start menu. `py -3.14 --version` should print Python 3.14.x.
- **macOS:** open the Python 3.14 `.pkg` from python.org. Open **Terminal** from Applications → Utilities. `python3.14 --version` should print Python 3.14.x. If the command is not found, use `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14` instead. If HTTPS certificates fail, run the Python installation's **Install Certificates.command**; do not disable TLS verification.
- **Linux:** use your distribution's supported Python 3.11–3.14, with its `venv` and Tk packages if you want the desktop demo. Check `python3 --version` first. A machine without a graphical desktop cannot display the Tk window.

The package name for pip is `kdpika-licensing`; the Python import is `kdpika_licensing`. `pip` installs libraries; it is not a second application you need to register for. You do not need a PyPI account, payment card or management API key to install this public SDK. Internet access is needed for the first installation and activation.

## Easiest route: open the desktop demo

[Download the Python demo ZIP](https://licensing.kdpika.com/docs/downloads/kdpika-python-projects-1.1.0.zip), extract it completely, and keep all files together. Do not run files from inside the ZIP. The project version **1.1.0** is different from its tested **SDK 2.0.1** version.

- **macOS:** double-click **Start Demo.command**. If it has no execute permission, open Terminal in the extracted folder and run `sh "Start Demo.command"`.
- **Windows:** double-click **Start Demo.bat**. If Python is not installed, install it using the previous step and try again.
- **Linux:** open a terminal in the extracted folder and run `sh start-demo.sh`.

The launcher finds supported Python, creates `.demo-venv` beside the files and installs the tested SDK **there only**. The first start needs a short wait and shows its progress. Later starts reuse the environment. Do not use `sudo pip`, change system Python, edit `common.py`, paste secrets into commands, or export environment variables for the desktop demo.

In the window, paste **App ID** from KDPika → Products, choose **Test (Sandbox)**, paste a real Sandbox license and its matching customer email, then choose **Activate license**. A normal software plan must include `csv_export`. Choose **Export CSV** to write a real file. **Live** uses Live licenses and needs a workspace with Live access. Switching the dropdown does not convert a Sandbox license into a Live license or take a payment.

Only the App ID and environment are remembered by the demo settings. The SDK keeps private installation/token state separately. Never share that state folder. [Full dashboard walkthrough](https://licensing.kdpika.com/docs/v1/tutorials/python).

## Install the SDK in your own project

Use this route when adding licensing to **your own** code, rather than running the ready-made demo. A virtual environment is a separate folder of packages for one project. It prevents a package installed in one Python from being mistaken for the package in another Python. You do **not** need to activate it: use its exact Python path in every command.

Create a normal project folder and open your terminal in it. On Windows, File Explorer → that folder → address bar → type `powershell` → Enter. On macOS, type `cd ` in Terminal, drag the folder into Terminal, then press Enter. Copy only the commands, not the `PS>` or `%` prompt and not the explanatory output.

**Windows PowerShell:**

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "kdpika-licensing==2.0.1"
.\.venv\Scripts\python.exe -c "import sys,importlib.metadata as m; print('Python:',sys.version.split()[0]); print('SDK:',m.version('kdpika-licensing')); print('Executable:',sys.executable)"
```

**macOS:**

```bash
python3.14 -m venv .venv
./.venv/bin/python -m pip install "kdpika-licensing==2.0.1"
./.venv/bin/python -c "import sys,importlib.metadata as m; print('Python:',sys.version.split()[0]); print('SDK:',m.version('kdpika-licensing')); print('Executable:',sys.executable)"
```

**Linux, after confirming Python 3.11–3.14:**

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install "kdpika-licensing==2.0.1"
./.venv/bin/python -c "import sys,importlib.metadata as m; print('Python:',sys.version.split()[0]); print('SDK:',m.version('kdpika-licensing')); print('Executable:',sys.executable)"
```

Expected: a supported Python, SDK **2.0.1**, and an executable inside this project's `.venv`. Run your app using that same executable: `./.venv/bin/python your_app.py` on macOS/Linux or `.\.venv\Scripts\python.exe your_app.py` in PowerShell. Your IDE must select that executable too. Installing in Python 3.14 does not update Python 3.9.

## Update, reinstall or remove the SDK

Close the app first. Stay in the same project folder and use the **same environment**. Keep your private activation state and App ID/environment unchanged during an update. Package installation/removal does not change your KDPika account or subscription.

| Task | macOS/Linux, own project | Windows PowerShell, own project |
| --- | --- | --- |
| Install the demo-tested version | `./.venv/bin/python -m pip install --upgrade "kdpika-licensing==2.0.1"` | `.\.venv\Scripts\python.exe -m pip install --upgrade "kdpika-licensing==2.0.1"` |
| Update to the latest published stable version | `./.venv/bin/python -m pip install --upgrade kdpika-licensing` | `.\.venv\Scripts\python.exe -m pip install --upgrade kdpika-licensing` |
| Repair the same tested version | `./.venv/bin/python -m pip install --force-reinstall "kdpika-licensing==2.0.1"` | `.\.venv\Scripts\python.exe -m pip install --force-reinstall "kdpika-licensing==2.0.1"` |
| View the installed package/version | `./.venv/bin/python -m pip show kdpika-licensing` | `.\.venv\Scripts\python.exe -m pip show kdpika-licensing` |
| Remove the SDK from this environment | `./.venv/bin/python -m pip uninstall kdpika-licensing` | `.\.venv\Scripts\python.exe -m pip uninstall kdpika-licensing` |

For the **downloaded demo**, use `.demo-venv` instead of `.venv`. Or run `python3 start.py --update` / `py -3 start.py --update` to restore the demo-tested SDK and open the app; `--check` shows its Python/SDK without opening it, and `--uninstall` removes just its SDK after pip asks for confirmation. Starting normally after removal installs the tested SDK again. These commands do not silently select a future SDK release.

Before permanently abandoning an activated computer, choose **Release this computer** and confirm it succeeds. Closing the app releases a floating seat; removing the SDK, deleting `.venv`/`.demo-venv`, or deleting local files **does not deactivate a server-side machine**. Do not delete the private `.kdpika-python-tutorial` folder to fix installation errors: that can lose the identity needed to release the old machine. Removing a package leaves dependencies and saved state; it does not cancel billing. If the computer is unavailable, use the authorized customer portal or publisher dashboard.

Optional SDK extras for your own app: append `[secure-storage]` for an available OS keyring, or `[ui]` for the SDK's optional Qt UI, e.g. `./.venv/bin/python -m pip install "kdpika-licensing[secure-storage]==2.0.1"`. The supplied desktop demo uses Tkinter, so Qt is not needed. Flask belongs only to the web example. Native keyring availability and target-OS packaging need separate verification.

## Common setup problems, in plain words

| What you see | What it means / next step |
| --- | --- |
| `Requirement already satisfied` but SDK 1.0.0 remains | You may be using Python 3.9. It cannot install the new package. Use the launcher or a supported Python's separate environment; repeating the same old pip command will not help. |
| `unexpected keyword argument 'product'` or no `close` method | An old SDK is loaded. Run `start.py --check`, then start through the launcher. Do not rewrite `LicenseClient` around the old package. |
| `KDP_APP_ID` / `KeyError` before the window opens | You are using the older demo. Download project 1.1.0 and enter App ID in its window. Never replace an environment-variable name in `os.environ[...]` with an App ID. |
| `No module named kdpika_licensing` | The app and pip are using different Python environments, or installation failed. Use the same full environment Python path for install and run. |
| `No matching distribution` / Python 3.9 | Install Python 3.11–3.14. Do not downgrade the SDK or bypass its Python requirement. |
| `python3.14` / `py` not found | Install Python 3.14; restart the terminal. macOS fallback is `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14`. |
| `No module named tkinter` | Use a Python installation with Tk support, or add the matching Tk package on Linux. The SDK itself does not require a GUI. |
| LibreSSL / `NotOpenSSLWarning` in the old command | That log used macOS developer-tools Python and an old package. Use the supported demo environment; do not suppress TLS checks. |
| Activation refused | App ID, environment, key and matching email must belong together. Test and Live are separate. A free workspace is Test only. |
| Activated but export denied | The license needs the `csv_export` feature. Apply plan changes to existing licenses when appropriate, then Check access. Metered licenses use the separate credit example. |
| `Permission denied` / incomplete `.demo-venv` | Extract into a normal folder you own, such as Documents. Remove only the generated incomplete environment and start again; keep private license state. |

[Python packaging: virtual environments](https://docs.python.org/3/library/venv.html) · [pip uninstall reference](https://pip.pypa.io/en/stable/cli/pip_uninstall/). Share only the version, selected executable and a redacted error when asking for help. Never post a license key, matching customer email, activation token or saved state publicly.

## Web and credit examples

See [Web example](https://licensing.kdpika.com/docs/v1/tutorials/python/web) and [Credit example](https://licensing.kdpika.com/docs/v1/tutorials/python/credits). They use the same SDK but have their own local setup. The web sample is one licensed server installation, not a ready public multi-tenant login system. The credit sample persists job IDs in SQLite to recover an uncertain debit without blindly charging again. Never delete its journal to retry.

[Full visual walkthrough](https://licensing.kdpika.com/docs/v1/tutorials/python). Samples are MIT licensed; the SaaS platform source is separate.
