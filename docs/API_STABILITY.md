# API stability for 1.0.0-rc.1

The supported V1 product boundary is the native desktop application and its
documented local workflows. The in-process HTTP-shaped dispatcher is an internal
implementation detail; the installed application does not expose a network API.

## Stable product contracts

- Owner authentication remains fail-closed and state changes remain CSRF-bound.
- Projects may be listed, inspected and created by the authenticated local owner.
- Tasks may be listed, inspected and created as pending records by that owner.
- Task dispatch, provider execution, cloud sends and tools remain separate,
  explicitly authorized actions.
- Brain records retain owner, Project and provenance boundaries.
- Backups, data location and default-keep uninstall behavior follow the packaging
  documentation.

## Internal or administrative contracts

Routes below `/api/*`, response shapes used by native Qt views, registry IDs,
resource snapshots, traces, migrations and diagnostic manifests are internal or
administrative for this candidate. They may change in a later candidate with a
migration and updated native client. They are not a remote-integration promise.

## Experimental contracts

Optional OpenAI-compatible endpoints, the free-pool preset, optional capability
packs, Agent tool loops, hardware/provider observations and visualization metrics
remain experimental. Their existence does not certify availability, quality,
cost, hardware fit or a future successful call.

No `/v1/*` public compatibility surface is shipped. A future public API should
be explicitly versioned under `/v1`, use a separately configured production
identity and authorization model, publish schemas and compatibility rules, and
remain disabled by default. It must not inherit native desktop session authority.
