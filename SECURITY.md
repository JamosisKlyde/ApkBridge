# Security policy

APKBridge is a development preview. Fixes are made against the latest source on
`main`; there is no commitment to backport fixes to older previews. GitHub
Releases identifies the latest packaged version.

## Reporting vulnerabilities

Do not publish credentials, private files, or working exploit details in a
public issue. If the repository offers **Report a vulnerability**, use that
private channel. Otherwise open an issue titled **Request for private security
contact**, with only a general description of the affected component, so the
maintainer can arrange a private channel before you share details. A private
reporting channel and response deadline are not currently guaranteed.

Include affected versions, the relevant code or feature, impact, and minimal
reproduction steps through the agreed channel. Do not test against systems or
accounts without authorization.

## Boundaries to understand

- APKBridge is a launcher, not an additional security sandbox for untrusted APKs.
- APK installation and execution use Waydroid and the Android app's permissions.
- The normal app is installed per user. Waydroid setup and ARM changes request
  administrator authorization.
- The optional ARM helper downloads and executes upstream code with elevated
  privileges. It records a source revision but does not pin or audit that code.
- Configuration snapshots are not complete Android app/data backups.
- Release checksums detect mismatched downloads; they are not digital signatures.

Dependency vulnerabilities should also be reported through the affected
upstream project's security process. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
