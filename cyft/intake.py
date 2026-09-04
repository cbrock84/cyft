"""Stage 1 and 3: get things in, and merge what is the same thing.

Deterministic, offline, no model. Deduplication is on the bytes for files and on
a normalised URL for links, so the same repository saved four times is one item.
"""

import os

from . import pdftext, store

TEXT_EXT = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".rst"}

# Files that are almost certainly credentials. Cyft copies what it takes in and,
# on `cyft read`, sends the text to a model provider. Sweeping a project folder
# must not put a private key on the wire, so these are refused and named.
SECRET_EXT = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".ppk", ".asc", ".gpg"}
SECRET_NAMES = {
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials", "credentials.json",
    "netrc", "pgpass", "htpasswd", "secrets.json", "secrets.yaml", "secrets.yml",
    "keyfile", "keystore",
}
SECRET_PREFIXES = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "service-account",
                   "serviceaccount", "gcp-key", "aws-credentials")
SECRET_DIRS = {".ssh", ".gnupg", ".aws", ".kube", ".docker", "gcloud"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
URLLIST_EXT = {".url", ".webloc", ".urls"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}

MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
}


def looks_like_secret(path):
    """Return why this file should not be taken in, or None if it is ordinary.

    Deliberately conservative about what it names: a false positive costs one
    skipped file and a printed reason, while a false negative can put a private
    key into a request body.
    """
    name = os.path.basename(path)
    lower = name.lower()
    stem, ext = os.path.splitext(lower)

    parts = os.path.normpath(path).split(os.sep)
    for part in parts[:-1]:
        if part.lower() in SECRET_DIRS:
            return "it is inside %s" % part

    if ext in SECRET_EXT:
        return "%s files hold keys or certificates" % ext
    if lower in SECRET_NAMES or stem in SECRET_NAMES:
        return "%s is a credential file" % name
    if lower.startswith(".env"):
        return "dotenv files hold secrets"
    for prefix in SECRET_PREFIXES:
        if lower.startswith(prefix):
            return "%s looks like a key or service account" % name
    return None


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

    if kind in ("text", "urllist"):
        # A link file with links in it is expanded by add_urllist, not here, so
        # anything reaching this point is treated as ordinary text.
        item["text"] = data.decode("utf-8", "replace")[:20000]
        item["kind"] = "text"
    elif kind == "pdf":
        # Best effort. An empty result means the text could not be trusted, which
        # is recorded rather than papered over, so the reading stage can say so.
        item["text"] = pdftext.extract(data)
        item["text_source"] = "pdf-extract" if item["text"] else "none"
    elif kind == "image":
        item["media_type"] = MEDIA_TYPES.get(ext, "image/png")

    store.save_item(root, item)
    if kind in ("image", "pdf", "file"):
        dest = os.path.join(store.item_dir(root, item["id"]), "original" + ext)
        with open(dest, "wb") as fh:
            fh.write(data)
    return item, True


def add_urllist(root, path):
    """Expand a link file into one item per link.

    Returns (added, dupes, expanded). `expanded` is False when the file held no
    links, so the caller can fall back to storing it as text.
    """
    with open(path, "rb") as fh:
        found = urls_in(fh.read().decode("utf-8", "replace"))
    if not found:
        return 0, 0, False
    added = dupes = 0
    for url in found:
        _, is_new = add_url(root, url)
        if is_new:
            added += 1
        else:
            dupes += 1
    return added, dupes, True


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


def add_paths(root, paths, on_skip=None):
    """Add everything under `paths`, returning (added, duplicates).

    Files that look like credentials are never taken in. `on_skip`, when given,
    is called with (path, reason) for each one, so a caller can report them. The
    return shape is unchanged so existing callers keep working.
    """
    added = dupes = 0
    for path in walk(paths):
        reason = looks_like_secret(path)
        if reason:
            if on_skip is not None:
                on_skip(path, reason)
            continue
        if classify(path) == "urllist":
            a, d, expanded = add_urllist(root, path)
            if expanded:
                added += a
                dupes += d
                continue
        _, is_new = add_file(root, path)
        if is_new:
            added += 1
        else:
            dupes += 1
    return added, dupes
