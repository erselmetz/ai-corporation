# Task 229a - stop browser navigation

Browser app-page launches and one-use token exchange are removed. Advanced actions open keyed native migration windows; functional management ports follow in phase B. Explicit online docs and approved open_url remain distinct.

Checks: tests/test_qt_advanced_controls.py and tests/test_qt_shell.py: 9 passed in the combined run; initial removed-route test exposed an incorrect TestClient loopback fixture, corrected and rerun: 1 passed. Browser launch patches cover webbrowser.open, QDesktopServices.openUrl and os.startfile. No web engine dependency. No push/deploy.

Retired three ticket replay/expiry/CSRF tests because the feature no longer exists; replaced by actual authenticated-route 404 assertions. Existing broader CSRF/session tests remain. Updated Advanced handoff test from browser ticket success to native singleton/no-browser behavior.

Phase B/C remain unfinished: listener and HTML assets still exist at this checkpoint. Do not claim full Task 229 parity yet.
