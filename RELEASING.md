# Release maintenance

Only publish a release when the maintainer has authorized it. Routine test CI
does not publish releases.

1. Update the version in `app/bridge_core.py`, `install-or-update.sh`, and
   `packaging/run-header.sh`. The extracted archive directory must match the
   version in the header.
2. Update README requirements, known limits, validation status, and CHANGELOG.
3. Run tests and verify any relevant behavior on a real KDE/Waydroid desktop.
4. Build an installer from source with the complete app, packaging files,
   installer/uninstaller, tests, LICENSE, LICENSING, and third-party notices.
   Exclude caches, local settings, credentials, and dependency environments.
5. Verify `--extract-only`, compare extracted files, and calculate SHA-256 sums.
6. Publish a tag at the corresponding source commit, release notes, installer,
   checksum, license, and corresponding source. Verify all asset download links.

The v0.1.3 workflow is specific to the already-authorized release and pinned to
its original source commit. It must not be reused blindly for another version.
The release-information workflow only updates v0.1.3 documentation and legal
attachments; it never replaces its original installer or moves the tag.

Original release installers remain byte-for-byte stable. If a package must be
rebuilt, give it a distinct version or packaging revision and checksum, explain
the change, and preserve the source that produced it.
