"""Stage 1 and 3: get things in, and merge what is the same thing.

Deterministic, offline, no model. Deduplication is on the bytes for files and on
a normalised URL for links, so the same repository saved four times is one item.
"""

import os

from . import store

TEXT_EXT = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".rst"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
URLLIST_EXT = {".url", ".webloc", ".urls"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}

MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
}


def classify(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in URLLIST_EXT:
        return "urllist"
    if ext in TEXT_EXT:
        return "text"
    return "file"


def normalise_url(url):
    """Same page, one item. Drops scheme case, trailing slash, and the fragment."""
    u = url.strip()
    for prefix in ("http://", "https://"):
        if u.lower().startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("#", 1)[0]
    if u.endswith("/"):
        u = u[:-1]
    return u.lower()


def urls_in(text):
    import re
    return re.findall(r"https?://[^\s\"'<>)\]]+", text or "")


def _blank_item(item_id, digest, kind, name):
    return {
        "id": item_id,
        "hash": digest,
        "kind": kind,
        "name": name,
        "added_at": store.now(),
        "status": "new",
        "seen": 1,
        "what": "",
        "claims": [],
        "url": "",
        "text": "",
        "media_type": "",
        "goal": "",
        "help": "",
        "cost": "",
        "vetoes": [],
        "route": "",
        "reason": "",
        "decided_at": "",
    }


def add_url(root, url):
    digest = store.hash_bytes(normalise_url(url).encode("utf-8"))
    existing = store.find_by_hash(root, digest)
    if existing:
        existing["seen"] = existing.get("seen", 1) + 1
        store.save_item(root, existing)
        return existing, False
    item = _blank_item(store.new_id(digest), digest, "url", url)
    item["url"] = url
    store.save_item(root, item)
    return item, True


def add_file(root, path):
    with open(path, "rb") as fh:
        data = fh.read()
    digest = store.hash_bytes(data)
    existing = store.find_by_hash(root, digest)
    if existing:
        existing["seen"] = existing.get("seen", 1) + 1
        store.save_item(root, existing)
        return existing, False

    kind = classify(path)
    item = _blank_item(store.new_id(digest), digest, kind, os.path.basename(path))
    ext = os.path.splitext(path)[1].lower()

    if kind == "text":
        item["text"] = data.decode("utf-8", "replace")[:20000]
    elif kind == "urllist":
        found = urls_in(data.decode("utf-8", "replace"))
        if found:
            # A file of links expands into one item per link, not one item.
            added = []
            for url in found:
                rec, is_new = add_url(root, url)
                if is_new:
                    added.append(rec)
            return added, len(added)
        item["text"] = data.decode("utf-8", "replace")[:20000]
        item["kind"] = "text"
    elif kind == "image":
        item["media_type"] = MEDIA_TYPES.get(ext, "image/png")

    store.save_item(root, item)
    if kind in ("image", "pdf", "file"):
        dest = os.path.join(store.item_dir(root, item["id"]), "original" + ext)
        with open(dest, "wb") as fh:
            fh.write(data)
    return item, True


def walk(paths):
    """Yield every file under the given paths, skipping noise and dotfiles."""
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in sorted(filenames):
                if name in SKIP_NAMES or name.startswith("."):
                    continue
                yield os.path.join(dirpath, name)


def add_paths(root, paths):
    added = dupes = 0
    for path in walk(paths):
        result, is_new = add_file(root, path)
        if isinstance(result, list):
            added += is_new
            continue
        if is_new:
            added += 1
        else:
            dupes += 1
    return added, dupes
