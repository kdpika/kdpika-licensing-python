# Current release: 2.0.0

- Required signed hardware binding, floating checkout/heartbeat/checkin and online idempotent usage credits.
- Updated installation, source links and cross-language capability documentation.
- Customer portal remains hosted; browser hardware fallback is unsupported.

# Changelog

## 2.0.0 — 2026-10-26

- Require product-salted hardware hashes and verify signed device/installation binding.
- Add floating checkout, heartbeat and checkin with signed lease expiry and seat exhaustion.
- Add online-only credit balance/consume, idempotent receipts and insufficient-credit errors.
- Breaking pre-launch server contract; older published clients are not compatible.
- Registry availability is recorded separately; a changelog is not proof of publication. Ed25519 is unchanged.

Notable changes follow Keep a Changelog categories. API v1 and SDK package
versions are independent. Registry availability is recorded on PyPI; a source
changelog entry is not proof of publication.

## Usage credits included in the current release

- Add online-only consume/get_balance and async equivalents, authenticated immutable
  receipts, and typed InsufficientCreditsError. Repeated request keys replay without
  another charge; no automatic retry on uncertain outcomes.
- Require signed credit policy; zero balance denies features without deleting the
  activation. Metered cache/offline access fails closed.

## Floating seats included in the current release

- Add shared-seat checkout/heartbeat/checkin, automatic renewal/recovery and safe
  shutdown/context management to synchronous and async clients.
- Enforce signed lease/token/expiry for cached/offline and retained feature results.
- Export AllSeatsInUseError for explicit checkout; no dependencies or publication.

## Unreleased — required hardware binding

- Collect product-salted hardware hashes on Windows/macOS/Linux; no new dependencies.
- Send fingerprints on activation/validation; enforce signed strict/flexible binding
  for online, cached and offline access. Fail closed when usable hardware is unavailable.
- Pre-launch breaking server contract, release availability is listed in the package registry to PyPI or source ZIP releases.

## [1.1.6] — 2026-10-24

### Changed

- Put documentation, GitHub and versioned source ZIP links at the top of the
  README, with explicit ZIP installation steps for Windows, macOS and Linux.
- Correct source/issues and release configuration after the Python repository
  rename. Add a release-specific artifact comparison against published 1.1.5 so
  existing successful runtime tests can be reused for this documentation release.
- No SDK runtime behavior, dependency constraints or license changes.

## [1.1.5] — 2026-10-20

### Changed

- Use GitHub's supported Intel macOS runner pool after arm64 jobs repeatedly
  failed to acquire runners. Build the same cryptography dependency with Rust
  and OpenSSL 3; retain all Python 3.11–3.14 tests, audits and publication gates.
  No SDK runtime logic or dependency-version changes.

## [1.1.4] — unpublished release preparation, 2026-10-20

### Fixed

- Audit exact installed third-party distributions (including transitive dependencies)
  without looking up the unpublished SDK candidate on PyPI. Record that scope in
  audit evidence; vulnerabilities, collection failures and service errors still block
  publication. SDK runtime and all protected publication gates are unchanged.

## [1.1.3] — unpublished release preparation, 2026-10-20

### Changed

- Pin native macOS CI to the supported `macos-15` arm64 image after repeated
  `macos-latest` runner-acquisition failures. All Python 3.11–3.14 checks and
  protected OIDC publication gates remain required; SDK runtime is unchanged.
- Preserve previous unpublished tags instead of rewriting release history.

## [1.1.1] — unpublished release preparation, 2026-10-20

### Fixed

- Pin Git text checkouts to LF so the approved MIT license retains the same
  SHA-256 on Windows, macOS and Linux. No license bytes or SDK logic changed.
- Supersedes the blocked, unpublished `v1.1.0` release attempt; that tag is
  preserved rather than rewritten. This source entry is not upload evidence.

## [1.1.0] — unpublished release preparation, 2026-10-20

### Fixed

- Make the test harness portable to Windows: bounded parametrized case names,
  POSIX-only permission assertions and asyncio's private socketpair wake-up path.
  Ordinary test network connections remain blocked. SDK runtime is unchanged.
- Preserve signed JSON wire number tokens through HTTP/cache round trips and
  escape U+2028/U+2029; strict duplicate/UTF-8/base64url/depth/size checks.
- Gate feature helpers on a verified valid current result, including expiry,
  signed grace, binding and clock failures; no enabling failure defaults.
- Bound HTTPS requests and public-key GET retries; refuse redirects and
  never retry uncertain activation/deactivation POSTs.
- Validate signed timestamps and key-derived IDs; pinned keys never rotate
  silently. Safe upstream messages and repr without payload/credential values.
- Atomic private version-1 storage, bounded process/thread locks, no new identity
  after corruption, and explicit keyring failure/fallback behavior.

### Added

- `kdpika_licensing` public package and an async adapter using the same core.
- Strict typing, py.typed, shared PHP-signed fixtures, regression/property tests,
  ruff/mypy/pytest/tox tooling and a Phase 1 migration/security audit.
- Complete candidate README with 35 FAQ entries, source-generated API reference,
  strict-build MkDocs guides, safe runnable Sandbox examples and example/doctest checks.
- Project security/contribution/conduct policies and version-derived artifact checks.
- SHA-pinned dedicated-repository CI templates (12 OS/Python combinations) and
  OIDC TestPyPI/PyPI release routing; owner/repository/tag/license gates stay closed.
- Separate installed-base and dedicated-tooling advisory audits; require pytest
  9.0.3+ after the initial tooling audit found the old temporary-directory advisory.

### Changed

- Owner-selected MIT License for this Python SDK and its documentation; no
  grant to the separately hosted platform/backend or service access.

- Candidate distribution `kdpika-licensing`; `license_sdk` remains a deprecated
  compatibility shim. Storage namespace, filenames and keyring service unchanged.
- Candidate Python support 3.11–3.14; local loopback HTTP needs explicit opt-in.
- Inconsistent pinned IDs are now configuration errors before any HTTP call.
- Require cryptography 50.0.2+ (below 51) after dependency auditing; upstream
  no longer supplies Intel macOS or 32-bit Windows wheels. Native compatibility
  beyond the executed arm64 macOS matrix remains unverified.

### Release verification

The owner approved publication and configured PyPI Trusted Publishing for
`kdpika/kdpika-licensing`, `release.yml`, environment `pypi`. Uploads remain
conditional on successful release checks and the protected environment review.
Native Qt, OS keyring and packaged-app acceptance are separate from core CI.

## 1.0.0 — observed current source, 2026-10-17

This is the version recorded in current package/project metadata (PHP uses the
existing versioned download label). It is not a reconstructed original release
date, a published registry release or an invented earlier-version history.

- Added complete source-install, lifecycle, storage/offline and known-limit
  documentation, license-information notice and runnable example links.
- Preserved runtime implementation, public APIs, response handling and package
  identity. Documentation changes do not silently fix known signing/cache gaps.
- PHP includes a new package-local standalone test entry; its legacy repository
  test remains unchanged and still assumes the repository-root autoload layout.

Future entries must identify the exact version, verified changes, compatibility
impact and tests. API v1 and SDK package versions are independent.
