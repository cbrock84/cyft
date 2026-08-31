"""The run store: a directory of plain files, readable without Cyft.

    <root>/
      profile.json            goals, constraints, kill criteria
      config.json             provider and model, mode 0600
      items/<id>/item.json    one record per distinct thing
      items/<id>/original.*   the bytes as supplied
      digests/<date>.md
"""

import errno
import hashlib
import json
import os
import time

ITEMS = "items"
DIGESTS = "digests"
PROFILE = "profile.json"
STATE = "state.json"


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
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def load_profile(root):
    return read_json(os.path.join(root, PROFILE))


def save_profile(root, profile):
    write_json(os.path.join(root, PROFILE), profile)


def load_state(root):
    return read_json(os.path.join(root, STATE), {"last_digest": None}) or {"last_digest": None}


def save_state(root, state):
    write_json(os.path.join(root, STATE), state)


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


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
