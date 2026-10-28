"""Bounded readiness for the fresh browser process's own startup file."""
import time


def wait_for_port(profile,process,deadline,*,clock=time.monotonic,sleep=time.sleep):
    path=profile/'DevToolsActivePort'
    while clock()<deadline:
        if process.poll() is not None:raise RuntimeError('The isolated browser exited before its local endpoint was ready')
        try:
            # Chrome creates this file before it has finished writing it. On
            # Windows the writer may briefly deny sharing; existence is not
            # readiness. Never extend the caller's deadline or change its ACL.
            if path.stat().st_size<=4096:
                lines=path.read_text(encoding='utf-8').splitlines()
                if len(lines)>=2 and lines[1].startswith('/devtools/browser/'):
                    port=int(lines[0])
                    if 0<port<65536:return port
        except (FileNotFoundError,PermissionError,ValueError):pass
        sleep(min(.05,max(0,deadline-clock())))
    raise RuntimeError('The isolated browser did not start its local endpoint before the deadline')
