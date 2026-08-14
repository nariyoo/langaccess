# -*- coding: utf-8 -*-
"""Putting a finished file where a half-written one must never appear.

Both stages that rewrite a run in place, `ingest` and `retry`, write the whole new file beside the
old one and move it across, so an interruption cannot leave a partial file at the path a later stage
reads as a run. The move is `os.replace`, which is atomic on both systems this package runs on.

On Windows it is also refusable. A replace fails with PermissionError, WinError 5, when anything
else holds the destination open for even the moment it takes to swap, and a virus scanner or a
search indexer reading a file just written is enough. Measured here on 2026-08-08: one run in three
of this package's own test suite, the same test each time, failing inside `langaccess ingest`.

Nothing was ever lost when that happened, because the finished file was already written beside the
destination, but what the person running the command saw was a traceback and a coding round that
looked gone. So the move is attempted a few times over about a second, and if it still cannot be
made the error says where the finished file is and what renaming it does.
"""
import os
import time

REPLACE_TRIES = 6
REPLACE_PAUSE = 0.2


class ReplaceBlocked(OSError):
    """A finished file that could not be moved into place, carrying the path it is waiting at."""

    def __init__(self, message, finished, target):
        OSError.__init__(self, message)
        self.finished = finished
        self.target = target


def replace_atomically(tmp, target, tries=REPLACE_TRIES, pause=REPLACE_PAUSE):
    """Move `tmp` onto `target`, waiting out whatever else is holding the destination.

    Returns `target`. Raises `ReplaceBlocked` naming the finished file, which is still on disk and
    complete, so no caller of this ever has to report work as lost.
    """
    last = None
    for attempt in range(tries):
        try:
            os.replace(tmp, target)
            return target
        except PermissionError as e:
            # Windows only: the destination is open in another process. Every other failure here,
            # a missing source or a path across devices, is a fault in the caller and is raised.
            last = e
            if attempt + 1 < tries:
                time.sleep(pause)
    raise ReplaceBlocked(
        '%s could not be replaced, because something else on this machine is holding it open (%s). '
        'Nothing was lost: the finished file is %s, and renaming that over %s completes the write.'
        % (target, last, tmp, target), tmp, target)
