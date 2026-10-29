# Security boundary

ERSELMETZ AI is a local-first desktop application. The native PySide6 process
uses an authenticated in-process policy facade and starts no TCP listener by
default. A request without the native owner session is denied. State-changing
operations require the matching CSRF value, and an owner lock invalidates prior
authority. The default API remains fail-closed when no authentication backend is
configured.

The local owner may create Projects and pending Tasks. Creating a Task does not
dispatch it. Dispatch, cloud calls, tools, capture, software changes and other
side effects retain their separate permissions, previews, consent or approval,
resource limits and stop controls. Unknown tool risk is treated as control.

Models, optional wheels and providers are never downloaded or called silently.
Cloud destinations require explicit configuration and per-turn approval where
applicable. Credentials must not appear in logs, build stamps, diagnostics,
roadmap data or commits.

The Windows installer is currently unsigned. SmartScreen reputation, a separate
clean Windows account, physical microphone/camera behavior, paid providers and
assistive technology are not release-certified. Report security issues privately
to the repository owner; do not include secrets or private user data in a report.
