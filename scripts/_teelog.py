"""Tee stdout/stderr to a timestamped file under ~/src/n76/logs/.

Usage in a script:
    from _teelog import setup_teelog
    setup_teelog(__file__)

Everything printed after that call is written both to the terminal
(so live output still works over SSH) and to
    ~/src/n76/logs/<script_stem>-YYYYmmdd-HHMMSS.log

The full path is printed at start + end so it's easy to fetch.
"""
from __future__ import annotations
import atexit
import os
import sys
import time
from pathlib import Path


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass


def setup_teelog(script_file: str, log_dir: str | os.PathLike | None = None) -> Path:
    stem = Path(script_file).stem
    if log_dir is None:
        # Default: ~/src/n76/logs (matches Air layout). Fall back to CWD.
        home = Path.home()
        candidate = home / "src" / "n76" / "logs"
        if candidate.parent.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            log_dir = candidate
        else:
            log_dir = Path.cwd() / "logs"
            Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_dir = Path(log_dir)

    ts = time.strftime("%Y%m%d-%H%M%S")
    path = log_dir / f"{stem}-{ts}.log"

    fh = open(path, "w", buffering=1)  # line-buffered

    orig_out = sys.stdout
    orig_err = sys.stderr
    sys.stdout = _Tee(orig_out, fh)
    sys.stderr = _Tee(orig_err, fh)

    def _finalize():
        try:
            print(f"\n[teelog] wrote {path}")
        except Exception:
            pass
        try:
            sys.stdout = orig_out  # restore before closing
            sys.stderr = orig_err
        except Exception:
            pass
        try:
            fh.close()
        except Exception:
            pass

    atexit.register(_finalize)

    print(f"[teelog] logging to {path}")
    return path
