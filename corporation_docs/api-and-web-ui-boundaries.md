# API and Web UI Boundaries

The FastAPI resource routes use `CorporationApplicationService` for
Corporation resources. Protected API requests require an authenticated
principal with the route's declared permission. The default authentication
backend rejects requests, and browser sign-in/session integration is not
configured.

The Corporation Web UI uses same-origin API requests. Browser modules do not
read registries, SQLite, provider internals, or arbitrary filesystem content.
The Documentation Portal is read-only and uses `documentation:read` for both
its document listing and document-content requests.

The file-backed Documentation source reads only top-level UTF-8 Markdown files
from `corporation_docs/`. It does not expose arbitrary repository paths or
support creating, editing, deleting, or publishing documents.
