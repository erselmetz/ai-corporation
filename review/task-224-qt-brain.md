# Task 224 — real-data Qt Brain and consented intake

2026-10-25, local only. Parent: `f074a8a` / `task-223-pyside6-shell`.
No push, deployment, Electron packaging or Node removal.

## Implemented contract

The main shell now uses one shared `BrainPanel`/`BrainScene` implementation for
its embedded preview and full-window projected-3D view. Opening full-window moves
the same widget, preserving its data/camera; Back/Esc returns it to the existing
chat window. There are no prose panels in the scene. Clicking a real chunk opens
a card beside it with source, saved date and plain-text reference. Forget requires
an inline second confirmation and the exact current record/revision. List mode
supports keyboard inspection and remains available when rendering is unsuitable.

Points derive only from retained chunks. Source colors and layout derive from
stable SHA-256 IDs, not Python `hash()` or random activity. Displayed links are
actual shared-source membership links, not invented semantic relationships.
Only actual retrieval hits light up. Layout distance is explicitly described as
presentation, not model understanding. An empty Brain renders no invented dots.

The default visual budget is 300 markers (owner-adjustable 50–2,000). Groups
retain their actual member IDs; when all chunks fit, none are unnecessarily
grouped. Glow pixmaps are cached per source color/highlight/DPI. The API bounds
its visual sample to 2,000 chunks; the coverage caption distinguishes loaded
chunks from the real total. Search can inspect actual matches outside that
visual sample. A complete large-corpus paginated explorer is not claimed.

File/folder selection and app-wide local-file/text drop now lead to a small inline
retention preview, not automatic writes. Ctrl+V outside editable inputs offers a
note; paste inside chat/search editors keeps its ordinary meaning. The owner
explicitly chooses Save locally. The preview states **My Brain, shared across chat
windows**, local nomic embeddings and 30-day retention. No cloud provider or model
download is used. These are global owner notes, not silently assigned Project notes.

Enumeration is streaming/bounded (200 selected roots/files, 5,000 visited entries,
50 MB aggregate), rejects remote/device paths, symlinks/junctions and secret-looking
files, and skips junk directories, unsupported types, empty files and files above
5 MB. Metadata checks do not ingest content. The reader validates the opened
regular-file identity/size/mtime and reads at most 5 MB before upload. Secret/type,
retention, owner, CSRF, loopback and upload bounds are enforced again by the API.

The native Brain application service atomically replaces a source using a SHA-256
key derived from owner + stable absolute path (or content-hash note key). Identical
bytes skip re-embedding/replacement. Text uses 800-character chunks / 100 overlap,
without a redundant trailing overlap-only chunk. Stored notes keep the existing
owner knowledge schema/provenance/access rules. No automatic import or update
overwrites user Brain data.

Normalized vectors and a signature-keyed matrix are cached, with an installed
FAISS pack used only when available. Keyword fallback is explicitly reported if
local embeddings are unavailable. Memory edits/deletion through Advanced also
invalidate the native derived cache; the service never requires the owner to use
one particular UI to make deletion effective. Concurrent source replacement is
serialized. Cancellation accepted before commit rolls back the replacement,
including cancellation during storage; completed saves are honestly distinguished
from cancellation of remaining work. Cancelled jobs cannot be replayed.

## Defects reproduced and repaired

- The carried-over chunker produced an extra overlap-only node at exact chunk
  boundaries (800 and 1,500 characters). Regression cases now enforce one/two
  chunks respectively, preserving the existing 1,800-character three-chunk case.
- Empty-body mutations from the old bridge omitted JSON content type and failed
  closed with HTTP 415. The bridge now sends bounded `{}` JSON plus the existing
  CSRF token for empty mutations; the middleware was not relaxed.
- Derived vectors could survive an Advanced deletion outside the native UI.
  Native ownership/cache lifetime now goes through the application service's
  existing memory invalidation boundary, with an actual SQLite regression.
- A focused inline preview scheduled for deferred deletion could cause a Windows
  Qt access violation when the next window opened. Repeated cancel/drop/window
  tests reproduced it. The shell now owns/reuses one stable consent widget and
  replaces only its pending payload; cancelling clears it and never replays the
  old selection. Shutdown also detaches its event filter and stops scene timers.
- A cancellation accepted during an insert could previously still commit.
  A pre-commit cancellation check and regression now prove rollback preserves
  the previous source. No stop/cancellation failure was converted into a skip.

## Real local evidence

`tools/qt_brain_check.py` used isolated application data, the actual Qt shell,
existing authenticated APIs and installed `nomic-embed-text:latest`, digest
`0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`.
It stops if Ollama is not running at `127.0.0.1:11434`; it installs nothing.

Five unchanged real repository documents (21, 139, 4,230, 4,347 and 7,697 bytes)
produced **26 chunks in 16,114.69 ms**. A folder containing two real documents
grew the Brain to **36**. Re-feeding the unchanged first file preserved the count.
The actual node card's two-step Forget removed its selected note: **36 → 35**.
The UI card, full-window view, list, Enter-to-search highlights and Esc/back return
were exercised with those actual retained records, not synthetic activity.

Ten retrieval-only questions before search prefixes produced expected-source
**Recall@5 0.80, MRR 0.75**. This measures the designated source appearing in the
top five, not judged answer correctness or citation accuracy. Some other sources
also repeat the same facts. Native chat-context/agent-loop parity remains 226.
The exact corpus hashes, frozen folder source commit, cases, ranks and timings
are in `task-224-brain-evidence.json`; the same frozen corpus is reserved for
225's before/after prefix comparison. FAISS was not installed in this isolated
profile, so the real result is normalized semantic search without FAISS.

## Validation and remaining phases

Full Python: **1,490 passed, 3 skipped, 0 failed**, 318.24 seconds. Final
focused backend/Qt/bridge regressions: **43 passed**, 15.84 seconds; eight Qt
cases also passed after the final repaint-index change. Legacy browser modules:
**295 passed**; Electron source: **44 passed**; docs: **23 passed**. The
three existing Windows symlink-privilege skips remain explicitly unverified;
Qt synthetic drag-event constructors add deprecation warnings, not failures.
No assistive-technology or physical Explorer drag session is claimed.

The two uncommitted Tk/OLE adapter cases were intentionally replaced by Qt MIME
text + Unicode-file drop/cancel contracts. Their domain cases were ported, and
the actual source intake test supplements them. No committed Node/Electron test
was removed. New coverage includes grouping membership, exact confirmation,
same-widget full-window return, cache erasure through Advanced and storage rollback.

At 800×580, reorganizing the Brain toolbar preserved a 250-pixel chat/composer
width. Qt scale factors 1/1.25/1.5 are tested in source layout grabs; actual Windows
125/150% settings and assistive technology remain unverified. Final screenshot
baselines, dead-control sweep, packaged/device performance and Node retirement
remain **227**. Shipped core knowledge/instant replies/exact math are **225**;
model/device queues, stop ownership, URL actions, rename/delete and the native
agent loop are **226**. No native parity or final no-Node claim is made here.

Local checkpoint: `task-224-qt-brain`. No push or deployment.

The shared real-data widget measured **119.41 repaint FPS at 300 nodes** (mean
8.37 ms, p95 10.02 ms) and **19.61 at 2,000** (mean 50.98 ms, p95 61.19 ms),
880×680, DPR 1. These are uncapped CPU repaint measurements using actual
tracked-file chunks in memory, not retained user data or GPU/display-present FPS.
Production animation is capped around 30 FPS; the 2,000-node case cannot sustain
that cap on this PC. The default stays 300, with grouping/list/reduced motion.
The earlier Qt/Tk spike used a different synthetic sphere and is not a direct
like-for-like speedup claim. Building a source-link index once per frame removed
repeated per-cluster edge scans while preserving the exact real relationships.

Screenshots: [shell](task-224-qt-assets/shell-brain.png),
[anchored card](task-224-qt-assets/brain-node-card.png),
[full Brain](task-224-qt-assets/brain.png), [list](task-224-qt-assets/brain-list.png),
[300 real chunks](task-224-qt-assets/render-300.png),
[2,000 real chunks](task-224-qt-assets/render-2000.png).
