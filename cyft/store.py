"""The run store: a directory of plain files, readable without Cyft.

    <root>/
      profile.json            goals, constraints, kill criteria
      config.json             provider and model, mode 0600
      state.json              digest read marker and decision counter
      .lock                   advisory lock taken around every read-modify-write
      items/<id>/item.json    one record per distinct thing
      items/<id>/original.*   the bytes as supplied
      digests/<date>.md
"""

import contextlib
import errno
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
import zipfile

try:
    import fcntl
except ImportError:                                    # Windows
    fcntl = None
    import msvcrt

ITEMS = "items"
DIGESTS = "digests"
PROFILE = "profile.json"
STATE = "state.json"
LOCK = ".lock"

_held = threading.local()


def ensure(root):
    for sub in ("", ITEMS, DIGESTS):
        path = os.path.join(root, sub) if sub else root
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
    return root


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    # Each writer owns its temporary file. A shared `<path>.tmp` lets a
    # second writer truncate the first writer's output or replace its file.
    # Keeping the temporary file beside the destination makes replace atomic.
    path = os.fspath(path)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                               suffix=".tmp", dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def locked(root):
    """Hold the store's exclusive lock for a whole read-modify-write.

    Atomic replace stops a reader seeing half a file, but two writers that both
    read, change and save still lose one change. Every write path takes this
    lock around its read as well as its save. It is advisory, held per store,
    and re-entrant within a thread so a locked caller can call a locked helper.
    """
    key = os.path.realpath(root)
    depth = getattr(_held, "depth", None)
    if depth is None:
        depth = _held.depth = {}
    if depth.get(key):
        depth[key] += 1
        try:
            yield
        finally:
            depth[key] -= 1
        return
    fd = os.open(os.path.join(root, LOCK), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        else:
            # LK_LOCK gives up after ten one-second tries; a long add or a slow
            # reading can hold the lock longer than that, so wait instead.
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        depth[key] = 1
        try:
            yield
        finally:
            depth[key] = 0
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            else:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)


def load_profile(root):
    return read_json(os.path.join(root, PROFILE))


def save_profile(root, profile):
    write_json(os.path.join(root, PROFILE), profile)


def load_state(root):
    return read_json(os.path.join(root, STATE), {"last_digest": None}) or {"last_digest": None}


def save_state(root, state):
    write_json(os.path.join(root, STATE), state)


def next_seq(root):
    """Hand out the next decision number. Call it while holding `locked(root)`.

    Numbers only grow, so "decided after the last digest" is a comparison of
    integers instead of wall-clock seconds, which two decisions can share.
    """
    state = load_state(root)
    state["seq"] = int(state.get("seq") or 0) + 1
    save_state(root, state)
    return state["seq"]


def stamp_decision(root, item):
    """Give a just-decided item its place in the store's change order."""
    item["decided_seq"] = next_seq(root)
    item.setdefault("decision", {})["seq"] = item["decided_seq"]
    return item


def item_dir(root, item_id):
    return os.path.join(root, ITEMS, item_id)


def item_path(root, item_id):
    return os.path.join(item_dir(root, item_id), "item.json")


def list_items(root):
    base = os.path.join(root, ITEMS)
    if not os.path.isdir(base):
        return []
    out = []
    for name in sorted(os.listdir(base)):
        rec = read_json(os.path.join(base, name, "item.json"))
        if rec:
            out.append(rec)
    return out


def save_item(root, item):
    d = item_dir(root, item["id"])
    if not os.path.isdir(d):
        os.makedirs(d)
    write_json(os.path.join(d, "item.json"), item)
    return item


def find_by_hash(root, digest):
    for item in list_items(root):
        if item.get("hash") == digest:
            return item
    return None


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def new_id(digest):
    """Short, stable, derived from content so a re-add lands on the same id."""
    return digest[:12]


# Files that belong to the user. config.json is a setting, not their data, and
# names the environment variable that holds a key; .lock is bookkeeping.
USER_FILES = (PROFILE, STATE)
USER_DIRS = (ITEMS, DIGESTS)


def _inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root + os.sep)


def export(root, dest):
    """Write everything the user put in, and everything decided, to one zip."""
    if _inside(dest, root):
        raise ValueError("export must be written outside the run store")
    with locked(root):
        with zipfile.ZipFile(dest, "x", zipfile.ZIP_DEFLATED) as zf:
            for name in USER_FILES:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    zf.write(path, name)
            for sub in USER_DIRS:
                for base, dirs, files in os.walk(os.path.join(root, sub)):
                    dirs.sort()
                    for name in sorted(files):
                        if name.startswith("."):
                            continue
                        path = os.path.join(base, name)
                        if os.path.islink(path):
                            continue
                        zf.write(path, os.path.relpath(path, root).replace(os.sep, "/"))
    return dest


def forget(root):
    """Delete every item, digest, the profile and the state. Settings stay."""
    with locked(root):
        for sub in USER_DIRS:
            path = os.path.join(root, sub)
            if os.path.isdir(path):
                shutil.rmtree(path)
        for name in USER_FILES:
            path = os.path.join(root, name)
            if os.path.exists(path):
                os.unlink(path)
        ensure(root)


def user_root(base, subject, issuer=""):
    """One store per signed-in user, named by a hash so no subject reaches a path.

    The issuer is part of the hash: two identity providers can issue the same
    subject string for different people.
    """
    if not isinstance(subject, str) or not subject:
        raise ValueError("a user root needs a non-empty subject")
    if not isinstance(issuer, str):
        raise ValueError("issuer must be a string")
    key = hashlib.sha256(("cyft-user-v1\0%s\0%s" % (issuer, subject)).encode("utf-8"))
    return os.path.join(os.path.abspath(base), "users", key.hexdigest()[:32])


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
