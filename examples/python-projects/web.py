"""Local single-customer web deployment. License checks run on this server, never in JS."""
import getpass
import secrets
from hmac import compare_digest

from flask import Flask, abort, redirect, render_template_string, request, send_file, session

from common import AccessDenied, export_csv, make_client

PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>My licensed web app</title><main>
<h1>My licensed web app</h1><p>{{ message }}</p>
<form method="post"><input type="hidden" name="csrf" value="{{ csrf }}">
{% if signed_in %}<label>Message <input name="text" maxlength="1000" value="My first web export" required></label>
<button name="action" value="export">Download CSV</button>
<button name="action" value="logout">Sign out</button>
{% else %}<label>App access code <input type="password" name="access_code" autocomplete="current-password" required></label>
<button name="action" value="login">Open this app</button>{% endif %}</form>
<p>The app access code is for this local example. It is not a KDPika password or license key.</p>
</main></html>"""


def create_app(client, access_code: str):
    if len(access_code) < 20:
        raise ValueError("Use a randomly generated app access code of at least 20 characters.")
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=4096,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")
    # Intentionally local HTTP only. Production needs HTTPS, stable session secrets,
    # real user authentication/authorization and rate limits; do not expose this demo publicly.
    app.extensions["license_client"] = client

    @app.after_request
    def private(response):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.route("/", methods=["GET", "POST"])
    def home():
        session.setdefault("csrf", secrets.token_urlsafe(32))
        message = "Open the local app, then try a licensed export."
        if request.method == "POST":
            if not compare_digest(request.form.get("csrf", ""), session["csrf"]):
                abort(400)
            action = request.form.get("action")
            if action == "login":
                if not compare_digest(request.form.get("access_code", ""), access_code):
                    message = "This access code could not be accepted."
                else:
                    session.clear()
                    session["signed_in"] = True
                    session["csrf"] = secrets.token_urlsafe(32)
                    return redirect("/", code=303)
            elif not session.get("signed_in"):
                abort(401)
            elif action == "logout":
                session.clear()
                return redirect("/", code=303)
            elif action == "export":
                text = request.form.get("text", "").strip()
                if not text or len(text) > 1000:
                    abort(400)
                try:
                    path = export_csv(client, text)
                    return send_file(path, as_attachment=True, download_name="my-export.csv")
                except AccessDenied as error:
                    message = str(error)
                except Exception:
                    message = "The export could not be completed. Please try again."
        return render_template_string(PAGE, message=message, csrf=session["csrf"],
                                      signed_in=bool(session.get("signed_in")))
    return app


if __name__ == "__main__":
    client = make_client()
    result = client.check()
    if result.error_code == "NOT_ACTIVATED":
        result = client.activate(getpass.getpass("License key for this server: "),
                                 input("Matching customer email: ").strip() or None)
    if not result.valid or not result.signature_valid:
        client.close()
        raise SystemExit("This server's license is unavailable. Check it in KDPika.")
    access_code = secrets.token_urlsafe(24)
    print("Local app access code (not a license):", access_code)
    print("Open http://127.0.0.1:5000 — this is a local, single-customer example.")
    try:
        create_app(client, access_code).run(host="127.0.0.1", port=5000, debug=False,
                                           use_reloader=False, threaded=False)
    finally:
        client.close()
