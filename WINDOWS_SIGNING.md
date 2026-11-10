# Windows packaging and public signing

The current preview runs Python source through pythonw.exe. Its icon/shortcut is application branding, not a digital signature. No public code signing certificate has been obtained, no account/subscription has been created and no artifact has been signed by this project.

## Reviewable next steps

1. Produce a native Windows build with embedded Umbra .ico, product/version metadata, licensing and a working isolated sensor helper. Test it with the actual hub and CPU first. A frozen application's `sys.executable` points to the application, not Python, so the current helper-launch mechanism must be adapted rather than blindly frozen.
2. Choose public distribution and verified publisher identity.
3. Sign the final executable/helper/installer artifacts with a trusted certificate and a trusted timestamp; verify signatures and hashes. Do not modify signed artifacts afterwards. Test/install on a clean Windows machine before publication. Keep signing keys out of source, releases and ordinary configuration exports.

## Microsoft paths (documentation checked November 10, 2026)

- Microsoft Store **MSIX** submissions are re-signed by Microsoft after certification; this is not the same as a signed EXE downloaded from GitHub. MSIX signing through the Store does not require purchasing a code-signing certificate. The app's elevation requirements and separate PawnIO dependency need review: `allowElevation` is a restricted capability with strict Store approval criteria. Store eligibility has not been established for this app.
- Store **MSI/EXE** submissions require the publisher to sign the installer; Microsoft does not re-sign those installers for the publisher.
- Azure **Artifact Signing** (formerly Trusted Signing) offers non-Store public signing after identity validation and requires an Azure account/subscription. Current public-trust eligibility covers organizations in the EU, but individual developers are limited to the United States and Canada. A Swedish individual should not assume eligibility. No paid enrollment is authorized or performed here.
- Traditional trusted-CA signing is another route, subject to the CA's eligibility, identity, key-storage and pricing terms. A self-signed test certificate does not provide public Windows publisher trust. Even a trusted signature does not guarantee immediate SmartScreen reputation for a new download.

Code signing authenticates publisher identity and detects post-signing changes. It does not certify that the application's hardware behavior is correct or that Microsoft endorses the project.

## Primary references

- https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options
- https://learn.microsoft.com/azure/artifact-signing/quickstart
- https://learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation
- https://learn.microsoft.com/windows/apps/package-and-deploy/app-capability-declarations
- https://pyinstaller.org/en/stable/runtime-information.html
