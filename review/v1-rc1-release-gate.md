# V1.0.0-rc.1 release gate

Date: 2026-10-29

## Validated source

- Canonical Python/Qt/browser/docs collection: 1,751 passed, 3 Windows
  symlink-privilege skips, 4 deprecation warnings, 0 failed in 511.25 seconds.
- Focused owner workflow/version/security/build checks: 63 passed.
- Native workspace, resource, Brain, capture and approval regressions: 99 passed.
- Public docs, browser and integrity checks: 65 passed.
- Documentation generation check, Python compileall, `pip check` and
  `git diff --check`: passed.

## Review artifacts

The uncommitted review build used version `1.0.0-rc.1` and source digest
`425c4367e9b4a5a9628d4b7a41fada855e5438467d7848c4a2fd49d8b6bbc6f5`.
Its smoke check showed a visible chat window, 5,049.53 ms startup, 178.97 MiB
working set, no listening TCP entries, no child process and no bundled Node
entry. The package size was 161,189,095 bytes. No user action was sent.

The unsigned review installer was 54,161,531 bytes with SHA-256
`7C8D65E8FD48CBD5BB6B035EF2B6D33EA94ACB8D462990DD41BC60C598B88D1D`.
It was compiled with an already installed, Authenticode-valid Inno Setup 6
compiler. Review artifacts are not release artifacts.

## Unverified and nonblocking

Fresh secondary Windows-account installation, Authenticode/SmartScreen,
physical microphone/camera/screen paths, assistive technology, paid/cloud
providers, all optional capability packs, other Windows versions and the old
three-Electron-window hardware matrix remain unverified. No deployment was
performed. The exact clean-source build and installer must pass after the
release commit before the tag and push.
