"""PyInstaller entry point for the native Python desktop."""
from app.native_desktop.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
