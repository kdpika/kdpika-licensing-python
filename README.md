# KDPika Licensing Python SDK

Official Python client for license activation, signed validation, controlled
offline access, feature checks and deactivation. **Python 3.11–3.14**, SDK **1.1.6**,
MIT licensed.

[Documentation](https://licensing.kdpika.com/docs/v1/sdks/python) · [GitHub source](https://github.com/kdpika/kdpika-licensing-python) · [Download SDK ZIP](https://github.com/kdpika/kdpika-licensing-python/releases/download/v1.1.6/kdpika-python-sdk-1.1.6.zip) · [PyPI package](https://pypi.org/project/kdpika-licensing/)

## Install from the source ZIP

Download [kdpika-python-sdk-1.1.6.zip from KDPika](https://licensing.kdpika.com/docs/downloads/kdpika-python-sdk-1.1.6.zip)
or the identical versioned asset from GitHub Releases. Verify its SHA-256 against
the [download table](https://licensing.kdpika.com/docs/v1/sdks/overview#download-and-verify),
then extract the `kdpika-python-sdk` directory beside your application.
From that parent directory, create and activate a private virtual environment:

~~~bash
python -m venv .venv
~~~

On macOS/Linux, run `source .venv/bin/activate`. In Windows PowerShell, run
`.\.venv\Scripts\Activate.ps1`. Then install the extracted SDK and its dependencies:

~~~bash
python -m pip install ./kdpika-python-sdk
python -m pip check
~~~

Import `kdpika_licensing` in your application. The distribution name remains
`kdpika-licensing`. The named SDK ZIP has the checksum and directory layout above;
GitHub's automatic **Source code (zip)** is a different repository snapshot.
This SDK does not include the proprietary platform/backend source.

Prefer pip without a source download? See [Installation](#installation) below.

[Platform API documentation](https://licensing.kdpika.com/docs) ·
[Configuration](#configuration-reference) · [Errors](#error-codes-and-recovery) ·
[FAQ](#frequently-asked-questions) · [Changelog](#changelog-and-contributing) ·
[License](#license)

## Features and limits

- Activate a persistent installation, validate access, deactivate/release its seat.
- Authenticate Ed25519 signatures and product/environment/installation binding.
- Preserve PHP-signed JSON numbers/Unicode through network/cache round trips.
- Use authentic signed offline grace; never fall back after a server refusal.
- Fail-closed result helpers for feature flags and numeric/structured entitlements.
- Optional OS keyring and Qt dialog; typed sync API and async to_thread adapter.
- Bounded HTTPS transport, no redirects and no automatic mutation retries.

This is a client licensing library, **not** your app's user authentication,
payment gateway, server-side fulfillment API or anti-tampering system. A person
controlling the computer can patch its software/state. Enforce valuable online
operations on an authenticated backend as well. Never embed a developer
management API key in a distributed client.

## Installation

Python >=3.11,<3.15. Create a private virtualenv:

~~~bash
python -m venv .venv
# Activate the virtualenv using your shell, then:
python -m pip install --upgrade "pip>=26.2.1,<27"
python -m pip install "kdpika-licensing==1.1.6"
~~~

Windows PowerShell activation: `.venv/Scripts/Activate.ps1`.
macOS/Linux activation: `source .venv/bin/activate`.

Optional extras and upgrades (published versions only):

~~~bash
python -m pip install kdpika-licensing
python -m pip install "kdpika-licensing[keyring]"
python -m pip install "kdpika-licensing[qt]"
python -m pip install --upgrade kdpika-licensing
~~~

For an unpublished checkout, use `python -m pip install .` instead.
A pre-release must be requested explicitly by version or `--pre`. Extras:
keyring, qt, test, dev, docs; legacy secure-storage/ui remain aliases.
Base runtime has only cryptography as a direct dependency (50.0.2+ below 51).
Upstream no longer supplies Intel macOS or 32-bit Windows wheels; evaluate a
supported platform/source build instead of downgrading to an affected version.

## Five-minute Sandbox quickstart

1. Create/select a product in your KDPika workspace and copy its Public App ID.
2. Issue a disposable **Sandbox** license for that product. If email matching
   is enabled, use its exact customer email.
3. Set private environment variables: KDP_APP_ID, KDP_STATE_DIR (absolute
   persistent private directory), KDP_LICENSE_KEY, optional KDP_CUSTOMER_EMAIL.
   Do not put values in source, shell history, public issues or screenshots.
4. Run this code, or the shipped `examples/basic.py` script:

~~~python
import os
from pathlib import Path
from kdpika_licensing import LicenseClient

client = LicenseClient(
    product=os.environ["KDP_APP_ID"],
    environment="SANDBOX",  # Always explicit: the compatibility default is LIVE.
    storage_dir=Path(os.environ["KDP_STATE_DIR"]),
)
result = client.check()
if result.error_code == "NOT_ACTIVATED":
    result = client.activate(
        os.environ["KDP_LICENSE_KEY"], os.getenv("KDP_CUSTOMER_EMAIL")
    )

if result.valid and result.signature_valid and result.feature("pdf_export"):
    print("PDF export is permitted for this checked decision.")
else:
    print("This feature is unavailable. Check your license or contact its publisher.")
~~~

`pdf_export` is an example entitlement, not a built-in server feature. Define it
in your product's license plan if needed. A valid license without it must not
enable it. Reuse this client/state directory across launches.

**Correct:** require a fresh valid, signature-valid decision, then the feature.
**Wrong:** `if client.activated:` or reading `result.payload["features"]` to
unlock work. Token presence and readable payload data do not authorize access.
`feature(..., default=True)` is still False on an invalid result;
`feature_value(..., 100)` is None on failure.

## Concepts and lifecycle

Public App ID identifies software. A customer key authorizes an installation.
Activation sends a random stable installation ID plus descriptive machine name,
platform and app version—not a hardware fingerprint. State is scoped to
origin/App ID/environment. Sandbox and Live access cannot be interchanged.

`check()` uses verified fresh cache or validates online. `validate()` requests
a fresh online check, but can still use authentic unexpired signed grace on a
network failure. An HTTP refusal or rejected signature never grants old access.
`deactivate()` releases the seat before clearing credentials; a successful
deactivation's valid=True is an acknowledgement, **not** signed access.

## Feature and numeric-limit gating

~~~python
result = client.check()
allowed = result.valid and result.signature_valid
value = result.feature_value("seat_count") if allowed else None
limit = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
if allowed and result.feature("pdf_export") and limit is not None:
    print("Checked feature and numeric limit are available.")
~~~

Validate types/ranges according to YOUR entitlement contract. A missing/invalid
limit is not unlimited. Returned feature mappings are detached copies. A held
result is not permanent permission: helpers check signed deadlines at use.

## Configuration reference

LicenseClient accepts these constructor options; no developer API key is needed.

| Option | Type / default | Meaning |
|---|---|---|
| product | str, required | Public App ID |
| environment | str, "production" | LIVE default; SANDBOX for testing; TEST/PRODUCTION aliases |
| base_url | str, https://licensing.kdpika.com | HTTPS origin only, no path/query/user info |
| application_name | str, "Licensed Application" | App label and default state-path component |
| application_version | str, "" | Your app version sent on activation |
| verification_key | dict[str,str] or None | Optional authorized key_id/public_key pin; Ed25519/base64url |
| storage_dir | pathlib.Path or None | Private persistent root; SDK adds namespace |
| timeout | float, 15.0 | Per-request socket timeout, >0 and <=120; not a total wall-time guarantee |
| prefer_keyring | bool, True | Try optional usable native keyring |
| transport | private Transport or None | Advanced trusted injection; preserve wire JSON with HttpResponse.from_bytes |
| clock | callable returning aware datetime or None | UTC clock by default; injection for tests |
| allow_loopback_http | bool, False | Keyword-only explicit local HTTP testing, never remote HTTP |

Pins never rotate automatically. Ordinary clients fetch the current key only
from their configured authenticated HTTPS origin. No envelope-supplied key is trusted.

## Error codes and recovery

SDK-owned messages are safe to display. Log only the bounded request_id; never
print response payloads, tokens, keys or exception chains.

| Code(s) | Meaning / safe action |
|---|---|
| NOT_ACTIVATED | Ask for a customer key through a private prompt |
| INVALID_LICENSE | Check key, App ID and required customer email |
| DEVICE_LIMIT_REACHED, ACTIVATION_LIMIT_REACHED | Release an authorized old seat or contact publisher |
| MAX_DEVICES_REACHED | Legacy compatibility code; same safe seat-limit action |
| APP_VERSION_NOT_SUPPORTED | Update the app or contact publisher |
| DEVICE_NOT_AUTHORIZED, DEVICE_MISMATCH | Reconcile this installation's authorization |
| INVALID_TOKEN | Activate this same installation again through an authorized flow |
| LICENSE_PENDING | Purchase/license not ready; contact publisher |
| LICENSE_EXPIRED, LICENSE_REVOKED, LICENSE_SUSPENDED, LICENSE_CANCELLED, LICENSE_NOT_ACTIVE | No access; show a plain renewal/support message |
| INVALID_REQUEST, PLAN_NOT_FOUND | Check integration/product configuration |
| RATE_LIMITED | Wait; no busy retry loop |
| NETWORK_ERROR | No authoritative response; only authentic signed grace may permit access |
| INVALID_RESPONSE, HTTP_ERROR | Response cannot authorize access; reconnect/contact publisher |
| SIGNATURE_INVALID | Authentication/binding failed; never bypass verification |
| KEY_ROTATION_REQUIRED | Publisher-controlled update of a configured pin required |
| INVALID_SIGNED_TIME, CLOCK_ROLLBACK_DETECTED | Correct date/time, reconnect or contact publisher |
| OFFLINE_CACHE_INVALID, OFFLINE_CACHE_MISSING, OFFLINE_GRACE_EXPIRED | Connect to refresh authorization |
| STORAGE_ERROR | Fix private storage permissions/keyring; do not delete identity to bypass limits |
| ACTIVATION_CANCELLED | Optional Qt dialog cancelled; not an access grant |

ConfigurationError may be raised during initialization, StorageError during
identity/storage setup or explicit reset_local. Most lifecycle/network refusals
return LicenseResult instead. Exceptions share LicenseSdkError; safe code and
request_id are available. Constructed application messages are not verified data.

## Storage, offline access and time

Default state roots (app-name sanitized; product/environment namespace appended):

| OS | Root |
|---|---|
| macOS | ~/Library/Application Support/<app-name>/License |
| Windows | %APPDATA%/<app-name>/License (home fallback if APPDATA absent) |
| Linux/other | $XDG_DATA_HOME/<app-name>/license (default ~/.local/share) |

Files retain their version-1 layout: installation.json, signed-state.json,
activation-token, plus .sdk.lock. Preserve installation identity when upgrading.
Corrupt cache can recover online; corrupt identity raises StorageError rather
than silently consuming another seat. Never delete identity to bypass limits.

POSIX namespace/file permissions are 0700/0600. Windows needs a user-private ACL.
Fallback files are not encrypted. The optional usable keyring is preferred;
`storage_security` reports os-keyring or permission-protected-file. Native
backend availability/behavior depends on OS/session; no vault certification.

Offline access requires authenticated cached state, matching bindings, active
status, unexpired license and signed absolute offline_grace_until. Clock rollback
tolerance is 300 seconds. Missing/malformed signed time fails closed; lifetime
requires expires_at=null. Zero offline grace permits a fresh online check but
not later cached/offline use. A pin never changes automatically; unknown keys
are refetched only online from the configured HTTPS origin, at most once per
ten seconds per client. No historical-key overlap exists on the server.

## Desktop, CLI, backend and async

- Desktop: preserve per-user state and add `.[qt]` for the optional blocking
  activation dialog. The server enforces email matching; UI required fields do
  not replace that policy. Run `python examples/pyqt_activation.py`.
- CLI: `python examples/session.py activate`, then check/validate/status or
  deactivate. Keys come from private environment or hidden prompt, not argv.
- Backend: `examples/backend_flask.py` protects a localhost demonstration using
  THIS backend's own license. It is not a multi-tenant identity or authenticated
  production web service; add your own authentication/authorization/rate limits.
- Async: `AsyncLicenseClient(client)`; await check/activate/validate/deactivate
  and feature/feature_value. It uses asyncio.to_thread and the same policy.
  Cancelling an await does not undo an in-flight request.
- Thread/process access uses bounded local advisory locks. Busy locks can fail
  after five seconds. No NFS or cross-user shared-state guarantee.
- PyInstaller: keep persistent state outside extraction/application resources.
  Packaging, Qt event-loop responsiveness and native vault operation still need
  your target-OS acceptance tests; none is falsely claimed verified here.

## Migration, upgrading and uninstalling

Uninstall the old distribution before installing the new one: both own the
compatibility namespace. Update imports to kdpika_licensing. Old license_sdk
imports/submodules still work with DeprecationWarning. Client local/credentials/
mutable transport are deprecated implementation escape hatches.

Preserve state paths and app configuration. Enabling defaults on refused results
are intentionally no longer honored; malformed identity/pins now fail safely.
Explicit allow_loopback_http=True is required for local HTTP testing.

Before uninstalling, confirm `client.deactivate().valid`, then run
`python -m pip uninstall kdpika-licensing`. Deletion/uninstall/reset_local
does not release a server-side seat. Test upgrades on disposable Sandbox state.

## Troubleshooting and compatibility

| Symptom | Check / safe action |
|---|---|
| Cannot install | Python version, supported cryptography wheel/platform and updated pip |
| Signature rejected | Correct origin/App ID/environment/key pin; do not reserialize signed JSON yourself |
| State lost after restart | Same user/app name/config and persistent private path |
| Activation limit reached | Authorized deactivation/recovery, never delete identity to bypass |
| Offline access refused | Prior authentic cache, correct clock, signed expiry/grace |
| Keyring unavailable | Backend/session availability; inspect storage_security |
| HTTP/timeout/rate-limit failure | Network/proxy/CA settings; no blind mutation retry |
| Need support | Safe request_id only; hi@kdpika.com |

| Capability | Verified / boundary |
|---|---|
| Python 3.11–3.14 | Executed on arm64 macOS in Phase 1; final results recorded in release report |
| Linux and Windows | See the exact release workflow for native CI matrix results |
| Base wheel/sdist | Fresh isolated installs with signed mock lifecycle |
| Native Qt/keyring/PyInstaller | Target-platform acceptance still required |
| PHP signature contract | Shared vectors, Unicode, number/cache round trips; not RFC 8785/JCS |

## Frequently asked questions

### 1. Where can I check published versions?
Use the [PyPI release history](https://pypi.org/project/kdpika-licensing/#history).
Only versions listed there are registry releases; a Git tag or checkout alone
does not establish a successful upload.

### 2. Which Python versions are supported?
The SDK requires Python 3.11–3.14. The release workflow checks Linux, macOS and
Windows; inspect its results for the exact version. Native Qt, OS keyring and
packaged applications need additional testing on your target platform.

### 3. What is the difference between an App ID and a license key?
The public App ID identifies software. A customer's key activates its purchase.
Developer management API keys belong on trusted servers, never distributed apps.

### 4. How do I choose Sandbox?
Pass environment="SANDBOX". TEST is an alias. The default remains LIVE for
backward compatibility. All shipped lifecycle examples explicitly use Sandbox.

### 5. Can a Sandbox license activate in Live?
No. Environment binding is checked. Use a key issued for the selected environment.

### 6. Why is activation refused with an email?
The product's server-side policy may require an exact customer-email match.
Use the purchaser's email or contact the software publisher.

### 7. Does activated=True mean access is valid?
No. It only means an activation token is present. Use a fresh check and require
valid and signature_valid, then inspect required entitlements.

### 8. Why is SIGNATURE_INVALID shown?
The response could not be authenticated or has wrong bindings/encoding.
Check configuration, origin and supported SDK version; never disable verification.

### 9. What does KEY_ROTATION_REQUIRED mean?
Your pinned key differs from the response key. Obtain an authorized app update
from its publisher. The SDK never silently replaces a pin.

### 10. Does the SDK support historical signing keys?
The server currently publishes only its current key. Cached known keys can
verify their own signed state; the SDK cannot invent a historical key ring.

### 11. What if all device seats are used?
Release an old installation through an authorized workflow or contact the
publisher. Deleting local identity is not a legitimate way around seat limits.

### 12. Do upgrades create a new installation?
Not if you preserve app name, origin, App ID, environment and the private state
directory. The namespace, filenames and keyring service remain compatible.

### 13. What if state disappears after packaging or an update?
Check whether your app changed its storage path/name or runs as a different user.
Do not write persistent state inside a temporary PyInstaller extraction folder.

### 14. What happens if identity is corrupt?
Initialization raises StorageError instead of silently consuming a new seat.
Restore a trusted backup or ask the publisher for an authorized recovery.

### 15. Can the app work offline?
Only after activation with an authenticated cached license inside signed expiry
and grace. Grace is an absolute signed deadline, not a fresh timer after failure.

### 16. Does validate() guarantee an online answer?
No. It requests online validation but permits signed offline grace on a network
failure. Inspect source if your own policy requires an online-only operation.

### 17. Will server rejection fall back to old access?
No. An authoritative HTTP refusal or rejected signature does not permit a
network-error fallback to old authorization.

### 18. What if my clock is wrong?
Restore correct automatic date/time and reconnect. Missing/malformed signed
times fail closed; rollback tolerance is 300 seconds, not indefinite access.

### 19. Are private files encrypted?
No. Permission-protected fallback is not encryption or a native vault. Install
the optional keyring extra for a usable OS vault; Windows requires private ACLs.

### 20. Will keyring work on headless Linux?
Not necessarily. A usable backend/session must exist. Check storage_security;
the SDK reports its selected backend and uses a documented fallback where safe.

### 21. Are Windows, Intel macOS and PyInstaller tested?
Only arm64 macOS runtime execution is recorded so far. Native Windows/Linux,
Qt/keyring and PyInstaller acceptance are not certified by the macOS matrix.
cryptography 49+ no longer supplies Intel macOS or 32-bit Windows wheels.

### 22. Can I disable TLS or signatures to work around a firewall?
No. Configure your trusted system CA/proxy correctly. Only explicit loopback
HTTP testing is allowed; never install a TLS/signature bypass in customer apps.

### 23. Are retries automatic?
Only the public-key GET can retry once with bounded jitter/Retry-After handling.
Activation, validation and deactivation POSTs are not automatically replayed.

### 24. What should I do after a timeout or cancellation?
Keep the same installation identity and reconcile the outcome. Cancellation of
an async await does not stop its worker's HTTP request. Do not blindly reactivate.

### 25. How should I handle RATE_LIMITED?
Pause and show a polite retry-later message. The SDK does not run an endless
retry loop or grant old access after an authoritative refusal.

### 26. Can multiple threads/processes share a client state?
Local operations serialize with bounded advisory locks. A busy lock can fail
after five seconds. Do not use NFS, shared users' directories or untrusted paths.

### 27. How do I uninstall safely?
Confirm successful deactivation first, then uninstall the distribution. Removing
local files or pip uninstall alone does not release the server-side seat.

### 28. May I keep a successful result forever?
No. Check before protected work. Helpers re-evaluate signed deadlines, but
result.valid records the original check-time decision, not a permanent grant.

### 29. Why does a numeric feature limit return None?
The decision may be invalid or the key absent. Validate the value's type/range;
do not interpret None, strings or booleans as an unlimited numeric allowance.

### 30. Does the base install require PyQt or a keyring?
No. cryptography is the only direct runtime dependency. qt/keyring are optional;
Flask is required only for the backend example/tests, not by the runtime SDK.

### 31. How do I upgrade from license_sdk?
Remove the old distribution before installing the candidate, update imports to
kdpika_licensing and preserve state. The old import warns but still works.

### 32. What can I safely log or send to support?
Use request_id and a non-sensitive description. Do not send keys, activation
tokens, full payloads, state files, customer emails or raw exception chains.

### 33. Can local licensing stop the machine owner patching my app?
No local SDK can provide that guarantee. Enforce valuable server-side operations
on your authenticated backend too. Do not market the SDK as tamper-proof.

### 34. Is the SDK open source or freely redistributable?
Yes. This SDK and its included documentation use the MIT License. You may
integrate and redistribute it in commercial applications under that license,
including its copyright and permission notice. The separately hosted KDPika
platform, server code and service subscription are not included or licensed
by this SDK repository. Using the service still requires its applicable access.

### 35. Where do I report a security problem?
Privately email hi@kdpika.com without secrets. Do not post a live exploit or
customer credentials in a public issue. No guaranteed response SLA is claimed.

## Changelog and contributing

1.1.6 updates documentation and repository links only; the runtime and dependency
constraints are unchanged from published 1.1.5.

1.1.5 upgrades the old local 1.0.0 label:
signed JSON/cache fixes, fail-closed helpers, time/pin/storage/network hardening,
new import namespace, async adapter, typing and release tooling. See the
included CHANGELOG.md for the detailed record and migration notes.

Contribute with synthetic Sandbox data only. Install `.[dev,docs,test]`, run
Ruff, strict mypy, pytest/coverage, tox and `mkdocs build --strict` before
proposing a change. Keep API v1/state/signing compatibility and add a regression
test. Included CONTRIBUTING.md and CODE_OF_CONDUCT.md explain the process.
Use the [repository and issue tracker](https://github.com/kdpika/kdpika-licensing-python/issues)
for non-sensitive SDK bugs and contributions. Security reports belong privately
at hi@kdpika.com, never in public issues.

## Security and license

Report vulnerabilities privately to [hi@kdpika.com](mailto:hi@kdpika.com).
Include SDK/runtime versions and a synthetic reproduction; never keys/tokens/
customer payloads. See included SECURITY.md. No response-time SLA is promised.

## License

This SDK and its included documentation are licensed under the [MIT License](LICENSE).
Copyright (c) 2026 KHALED AL HARAZI. Keep the copyright and permission notice
when redistributing the SDK. It is provided without warranty as stated in LICENSE.

The separately hosted KDPika SaaS platform, backend source, customer data and
service access are not part of this SDK distribution. MIT licensing of the SDK
does not grant free platform access or rights to KDPika trademarks. Publishing
to PyPI will make the SDK source downloadable; it does not publish the backend.

## SDK repositories and ZIP downloads

| Language | GitHub repository | ZIP from documentation | ZIP from GitHub Releases |
| --- | --- | --- | --- |
| Python | [kdpika-licensing-python](https://github.com/kdpika/kdpika-licensing-python) | [Python 1.1.6 ZIP](https://licensing.kdpika.com/docs/downloads/kdpika-python-sdk-1.1.6.zip) | [Python 1.1.6 ZIP](https://github.com/kdpika/kdpika-licensing-python/releases/download/v1.1.6/kdpika-python-sdk-1.1.6.zip) |
| Rust | [kdpika-licensing-rust](https://github.com/kdpika/kdpika-licensing-rust) | [Rust 0.1.0 ZIP](https://licensing.kdpika.com/docs/downloads/kdpika-rust-sdk-0.1.0.zip) | [Rust 0.1.0 ZIP](https://github.com/kdpika/kdpika-licensing-rust/releases/download/v0.1.0/kdpika-rust-sdk-0.1.0.zip) |
| PHP | [kdpika-licensing-php](https://github.com/kdpika/kdpika-licensing-php) | [PHP 1.0.1 ZIP](https://licensing.kdpika.com/docs/downloads/kdpika-php-sdk-1.0.1.zip) | [PHP 1.0.1 ZIP](https://github.com/kdpika/kdpika-licensing-php/releases/download/v1.0.1/kdpika-php-sdk-1.0.1.zip) |

Each versioned GitHub ZIP asset is byte-identical to the matching documentation
download. GitHub's automatic “Source code (zip)” is a repository snapshot with a
different folder name and may include newer README/CI metadata; use the named
SDK asset when following the documentation's extraction paths and checksum.
