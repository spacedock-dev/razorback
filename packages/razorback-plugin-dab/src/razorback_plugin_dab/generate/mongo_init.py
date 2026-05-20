# ABOUTME: Emits the .sh shim mongo:8's init.d auto-runs to mongorestore a BSON dump.
# ABOUTME: Closes PKG-15 AC-1; the official mongo image ignores .bson but auto-executes .sh.

from __future__ import annotations

import re


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def render_mongo_restore_sh(*, db_name: str, dump_folder_basename: str) -> str:
    """Return the shell text mongo:8 should auto-run from /docker-entrypoint-initdb.d/.

    Refuses names that would inject shell or traverse paths. db_name and
    dump_folder_basename are caller-controlled in principle but come from
    db_config.yaml on disk in practice — refusing unsafe values keeps a
    poisoned upstream dataset from turning into a container-side RCE.
    """
    if not _SAFE_NAME.match(db_name):
        raise ValueError(f"unsafe mongo db_name {db_name!r}")
    if not _SAFE_NAME.match(dump_folder_basename):
        raise ValueError(f"unsafe mongo dump folder basename {dump_folder_basename!r}")

    return (
        "#!/bin/sh\n"
        "set -eu\n"
        "# PKG-15: mongo:8 image ignores .bson in /docker-entrypoint-initdb.d/.\n"
        "# This shim is auto-executed at first-start to load the BSON dump.\n"
        f"mongorestore --db {db_name} "
        f"/docker-entrypoint-initdb.d/{dump_folder_basename}/{db_name}\n"
    )
