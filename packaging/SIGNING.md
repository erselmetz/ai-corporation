# Unsigned local builds and signing plan

Task 230 installers and application executables are unsigned local test builds,
not published releases. A successful SHA-256 check establishes file identity,
not publisher identity, malware safety or a trusted signature.

For a downloaded unsigned/unrecognized file, SmartScreen may show **Windows
protected your PC** and **Unknown publisher**. Depending on Windows policy,
**More info** may offer **Run anyway**; managed policy or Smart App Control may
block it entirely. Do not disable Windows protections to complete a test. A local
build without Internet download marking may not display that prompt; that is not
proof of reputation. See [Microsoft's developer guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

Code signing requires a separate owner decision:

1. Choose the legal publisher identity and an approved code-signing certificate
   or managed signing service. No purchase or account enrollment is authorized by
   this task.
2. Protect the signing key outside the repository and app, with restricted access
   and explicit release authorization. Never bundle a private key or log it.
3. Build from an exact reviewed commit. Sign our EXE and then the installer with
   SHA-256 and an approved RFC3161 timestamp. Preserve third-party vendor signatures.
4. Verify publisher chain, timestamp and signatures on the final bytes; record
   hashes after signing. Run installed-artifact checks again on those signed bytes.
5. Publish/update only with separate authorization and the existing trusted
   manifest/signature/installer verification. Signing does not waive app consent,
   permissions or spend limits, and does not guarantee immediate SmartScreen
   reputation or eliminate antivirus false positives.

No certificate was purchased, signing key generated, executable fake-signed,
protection disabled, update published or deployment performed.
