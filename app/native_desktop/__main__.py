"""python -m app.native_desktop — pure Python startup, isolated from repository data."""
import os
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog, messagebox


def main():
    root=tk.Tk(); root.withdraw()
    from app.local_owner_credential import LocalOwnerCredentialStore
    from .session import NativeSession
    from .shell import NativeShell
    store=LocalOwnerCredentialStore(); password=None; session=None
    try:
        if store.exists():
            password=simpledialog.askstring("Unlock ERSELMETZ AI","Owner password:",show="*",parent=root)
            if password is None: return
            if not store.verify(password): raise ValueError("Owner password did not match")
        data=Path(os.environ.get("LOCALAPPDATA",Path.home()/".local"/"share"))/"ERSELMETZ AI"
        data.mkdir(parents=True,exist_ok=True); os.chdir(data)
        session=NativeSession(password)
        root.deiconify(); NativeShell(root,session); root.mainloop()
    except Exception as error: messagebox.showerror("ERSELMETZ AI",str(error)[:500],parent=root)
    finally:
        if session: session.close()


if __name__=="__main__": main()
