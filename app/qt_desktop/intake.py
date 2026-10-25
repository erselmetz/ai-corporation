"""Bounded enumeration of explicitly chosen local roots; no file contents read."""
import os
from pathlib import Path
from app.knowledge.intake import _TEXT_SUFFIXES
from app.knowledge.native_brain import MAX_FILE_BYTES, SKIP_DIRS, secret_path


def selected_files(paths, stop=None):
    chosen=[]; visited=0; total=0; unique=set()
    def include(path):
        nonlocal total
        try:
            if path.is_symlink() or path.is_junction() or not path.is_file() or secret_path(path): return
            if path.suffix.lower() not in _TEXT_SUFFIXES | {'.pdf','.docx'}: return
            size=path.stat().st_size
            if not 0<size<=MAX_FILE_BYTES or total+size>50*1024*1024: return
            resolved=path.resolve(strict=True); key=os.path.normcase(str(resolved))
            if key in unique: return
            unique.add(key); chosen.append(resolved); total+=size
        except OSError: return
    for raw in list(paths)[:200]:
        if stop is not None and stop.is_set(): break
        # Never turn a remote file URL or Windows device path into an implicit
        # network/device read during drag-and-drop enumeration.
        if str(raw).startswith(('\\\\','//')): continue
        path=Path(raw)
        try:
            if path.is_symlink() or path.is_junction(): continue
            if path.is_dir():
                root=path.resolve(strict=True)
                pending=[root]
                while pending:
                    if stop is not None and stop.is_set(): return chosen
                    with os.scandir(pending.pop()) as entries:
                        for entry in entries:
                            visited+=1
                            if visited>5000 or (stop is not None and stop.is_set()): return chosen
                            item=Path(entry.path)
                            if entry.is_symlink() or item.is_junction(): continue
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name.casefold() not in SKIP_DIRS: pending.append(item)
                            elif entry.is_file(follow_symlinks=False): include(item)
                            if len(chosen)>=200: return chosen
            else: include(path)
        except OSError: continue
        if len(chosen)>=200: break
    return chosen
