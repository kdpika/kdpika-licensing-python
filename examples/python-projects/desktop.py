"""Real licensed desktop demo. No code edits or environment variables required."""
import sys

# Check before importing the SDK: older Python may have a different SDK installed.
if not (3, 11) <= sys.version_info[:2] < (3, 15):
    print('This demo needs Python 3.11–3.14. Open Start Demo.command (Mac), Start Demo.bat (Windows), or run python3 start.py. Do not edit common.py.')
    raise SystemExit(1)

from concurrent.futures import ThreadPoolExecutor
import importlib.metadata
import json
from pathlib import Path
import webbrowser

REQUIRED_SDK = '2.0.1'


def sdk_ready():
    try:
        # Later stable patch releases in the same API line may be used manually.
        version = importlib.metadata.version('kdpika-licensing')
        parts = version.split('.')
        return len(parts) == 3 and all(p.isdigit() for p in parts) and parts[:2] == ['2', '0'] and int(parts[2]) >= 1
    except importlib.metadata.PackageNotFoundError:
        return False


def setup_problem():
    return 'The SDK in this Python is missing or outdated. Start with start.py; it prepares SDK ' + REQUIRED_SDK + ' in a separate demo environment. No source edits needed.'


class DemoSession:
    """One worker owns this client. Switching app/environment closes the old lease first."""
    def __init__(self):
        self.client = None
        self.configuration = None

    def connect(self, product, environment):
        from common import application_folder, make_client
        product, environment = product.strip(), environment.strip().upper()
        folder = application_folder(product, environment)
        if self.configuration != (product, environment):
            self.close()
            self.client = make_client(product, environment)
            self.configuration = (product, environment)
        return self.client, folder

    def perform(self, action, product, environment, key='', email='', text=''):
        from common import export_csv
        client, folder = self.connect(product, environment)
        save_settings(product.strip(), environment.strip().upper())
        if action == 'activate':
            if not key.strip():
                raise ValueError('Paste your license key first. If this computer is already activated, choose Check access.')
            return client.activate(key.strip(), email.strip() or None)
        if action == 'check':
            return client.validate()
        if action == 'saved':
            return client.check()
        if action == 'export':
            if not text.strip() or len(text) > 1000:
                raise ValueError('Enter a message between 1 and 1,000 characters.')
            return export_csv(client, text, folder)
        if action == 'release':
            return client.deactivate()
        raise ValueError('Choose one of the actions in the window.')

    def close(self):
        if self.client is not None:
            self.client.close()
        self.client = None
        self.configuration = None


def settings_file():
    return Path.home() / '.kdpika-python-tutorial' / 'demo-settings.json'


def load_settings():
    try:
        data = json.loads(settings_file().read_text())
        product, mode = data.get('product', ''), data.get('environment', 'SANDBOX')
        if isinstance(product, str) and len(product) <= 100 and mode in {'SANDBOX', 'LIVE'}:
            return product, mode
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return '', 'SANDBOX'


def save_settings(product, environment):
    # Only public configuration; never persist the license key or customer email here.
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as output:
        json.dump({'product': product, 'environment': environment}, output)
    temporary.chmod(0o600)
    temporary.replace(path)


def result_text(result, action):
    if action == 'release' and result.valid:
        return 'This computer was released. Activate again before exporting.'
    if result.valid and result.signature_valid:
        return 'Access is ready. Choose Export CSV to save your message.'
    messages = {
        'NOT_ACTIVATED': 'This computer is not activated yet. Paste your key and its customer email, then choose Activate license.',
        'INVALID_LICENSE': 'This key was not accepted. Check the App ID, Test/Live choice, key and matching email.',
        'LICENSE_NOT_FOUND': 'This key was not accepted. Check the App ID, Test/Live choice, key and matching email.',
        'EMAIL_MISMATCH': 'Check that the customer email matches this license.',
        'LICENSE_EXPIRED': 'This license has expired. Renew it or use another valid license.',
        'LICENSE_REVOKED': 'This license is no longer active. Contact the software publisher.',
        'DEVICE_LIMIT_REACHED': 'This license has no free computer slots. Release an unused computer from the customer portal or increase its limit in KDPika.',
        'ACTIVATION_LIMIT_REACHED': 'This license has reached its activation limit. Review the license in KDPika.',
        'ALL_SEATS_IN_USE': 'All shared seats are in use. Close the app on another computer and try again.',
        'NETWORK_ERROR': 'KDPika could not be reached. Check your connection. Use Check saved access only if this app was activated before.',
        'HARDWARE_MISMATCH': 'This computer no longer matches its saved activation. Review it in the customer portal or contact the publisher.',
        'FINGERPRINT_UNAVAILABLE': 'This computer could not provide the device information required by the license. See the setup guide for supported systems.',
    }
    return messages.get(result.error_code, 'Access is not ready. Check the App ID, Test/Live choice, key, matching email and connection. The setup guide explains the next steps.')


def main():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print('Tkinter window support is missing. See https://licensing.kdpika.com/docs/v1/tutorials/python/desktop#install-python')
        return 1
    if not sdk_ready():
        print(setup_problem())
        try:
            root = tk.Tk(); root.withdraw()
            messagebox.showinfo('Prepare the demo first', setup_problem()); root.destroy()
        except tk.TclError:
            pass
        return 1
    from common import AccessDenied
    root = tk.Tk()
    root.title('KDPika · Your first licensed app')
    root.geometry('720x760'); root.minsize(600, 690)
    style = ttk.Style(root)
    style.configure('Title.TLabel', font=('', 20, 'bold'))
    style.configure('Step.TLabel', font=('', 13, 'bold'))
    style.configure('TLabel', font=('', 11))
    style.configure('TButton', font=('', 11), padding=(12, 8))
    style.configure('TEntry', padding=7)
    container = ttk.Frame(root); container.pack(fill='both', expand=True)
    canvas = tk.Canvas(container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
    frame = ttk.Frame(canvas, padding=24)
    content = canvas.create_window((0, 0), window=frame, anchor='nw')
    frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda e: canvas.itemconfigure(content, width=e.width))
    frame.columnconfigure(0, weight=1)
    ttk.Label(frame, text='Try your licensed app', style='Title.TLabel').grid(sticky='w')
    ttk.Label(frame, text='Paste your app details. No code changes needed.').grid(sticky='w', pady=(4, 16))
    saved_product, saved_mode = load_settings()
    product = tk.StringVar(value=saved_product)
    mode = tk.StringVar(value='Live' if saved_mode == 'LIVE' else 'Test (Sandbox)')
    ttk.Label(frame, text='1 · Connect your app', style='Step.TLabel').grid(sticky='w')
    connection = ttk.Frame(frame); connection.grid(sticky='ew', pady=(10, 4)); connection.columnconfigure(0, weight=1)
    ttk.Label(connection, text='App ID · copy from KDPika → Products').grid(row=0, column=0, sticky='w')
    app_field = ttk.Entry(connection, textvariable=product, font=('', 12)); app_field.grid(row=1, column=0, sticky='ew', padx=(0, 12), pady=5)
    ttk.Label(connection, text='Environment').grid(row=0, column=1, sticky='w')
    environment = ttk.Combobox(connection, textvariable=mode, values=('Test (Sandbox)', 'Live'), state='readonly', width=18, font=('', 11))
    environment.grid(row=1, column=1, sticky='ew', pady=5)
    mode_note = tk.StringVar()
    def explain_mode(*_):
        mode_note.set('Test (Sandbox) · use a Sandbox license. No real sale is created.' if mode.get() != 'Live' else 'Live · use a real Live license. Requires a workspace with Live access. This demo does not take payments.')
    mode.trace_add('write', explain_mode); explain_mode()
    note = ttk.Label(frame, textvariable=mode_note, wraplength=640); note.grid(sticky='ew', pady=(0, 16))
    ttk.Label(frame, text='2 · Activate a customer license', style='Step.TLabel').grid(sticky='w')
    ttk.Label(frame, text='License key').grid(sticky='w', pady=(10, 0))
    key = ttk.Entry(frame, show='•', font=('', 12)); key.grid(sticky='ew', pady=5)
    ttk.Label(frame, text='Customer email · the email on this license').grid(sticky='w')
    email = ttk.Entry(frame, font=('', 12)); email.grid(sticky='ew', pady=(5, 10))
    ttk.Label(frame, text='3 · Make a protected export', style='Step.TLabel').grid(sticky='w')
    message = ttk.Entry(frame, font=('', 12)); message.insert(0, 'My first licensed export'); message.grid(sticky='ew', pady=10)
    actions = ttk.Frame(frame); actions.grid(sticky='ew'); actions.columnconfigure((0, 1), weight=1)
    status = tk.StringVar(value='Start with the App ID and a test license. The guide shows where to find both.')
    state_label = ttk.Label(frame, textvariable=status, wraplength=640); state_label.grid(sticky='ew', pady=(14, 8))
    progress = ttk.Progressbar(frame, mode='indeterminate'); progress.grid(sticky='ew', pady=(0, 6))
    ttk.Label(frame, text='Python ' + sys.version.split()[0] + ' · SDK ' + importlib.metadata.version('kdpika-licensing')).grid(sticky='w')
    ttk.Button(frame, text='Open the step-by-step setup guide ↗', command=lambda: webbrowser.open('https://licensing.kdpika.com/docs/v1/tutorials/python/desktop')).grid(sticky='w', pady=(8, 0))
    frame.bind('<Configure>', lambda e: [widget.configure(wraplength=max(250, e.width - 48)) for widget in (state_label, note)], add='+')
    executor = ThreadPoolExecutor(max_workers=1); session = DemoSession()
    pending = []; buttons = []; closing = False

    def enabled(value):
        for control in buttons + [app_field, key, email, message]:
            control.state(['!disabled'] if value else ['disabled'])
        environment.configure(state='readonly' if value else 'disabled')

    def run(action):
        if pending or closing:
            return
        public_id = product.get().strip()
        if not public_id.startswith('app_') or not public_id.replace('_', '').isalnum() or len(public_id) > 100:
            status.set('Paste your App ID from KDPika → Products. It begins with app_.'); app_field.focus_set(); return
        if action == 'release' and not messagebox.askyesno('Release this computer?', 'This removes this computer’s activation. You will need to activate it again. Your subscription and other computers are unchanged.'):
            return
        values = (action, public_id, 'LIVE' if mode.get() == 'Live' else 'SANDBOX', key.get(), email.get(), message.get())
        status.set('Saving your export…' if action == 'export' else 'Contacting KDPika…')
        enabled(False); progress.start(12); pending.append((executor.submit(session.perform, *values), action))

    for i, (label, action) in enumerate([('Activate license', 'activate'), ('Check access', 'check'), ('Export CSV', 'export'), ('Check saved access', 'saved'), ('Release this computer', 'release')]):
        button = ttk.Button(actions, text=label, command=lambda value=action: run(value)); button.grid(row=i // 2, column=i % 2, sticky='ew', padx=(0 if i % 2 == 0 else 6, 6 if i % 2 == 0 else 0), pady=4); buttons.append(button)

    def close():
        nonlocal closing
        if closing:
            return
        closing = True; enabled(False); status.set('Closing and freeing any shared seat…')
        pending.append((executor.submit(session.close), 'close'))

    def poll():
        if pending and pending[0][0].done():
            future, action = pending.pop(0)
            try:
                result = future.result()
                if action == 'export':
                    status.set('Saved your CSV: ' + str(result))
                elif action != 'close':
                    status.set(result_text(result, action))
                    if result.valid:
                        key.delete(0, 'end')
            except (AccessDenied, ValueError) as error:
                status.set(str(error))
            except Exception:
                # Never put tokens, server bodies or private payloads in UI/logs.
                status.set('The action could not finish. Check your connection and try again. The setup guide has troubleshooting steps.')
            if action == 'close':
                executor.shutdown(wait=False); root.destroy(); return
            if not closing:
                progress.stop(); enabled(True)
        root.after(75, poll)
    root.protocol('WM_DELETE_WINDOW', close); app_field.focus_set(); root.after(75, poll); root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
