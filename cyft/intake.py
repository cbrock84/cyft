"""Stage 1 and 3: get things in, and merge what is the same thing.

Deterministic, offline, no model. Deduplication is on the bytes for files and on
a normalised URL for links, so the same repository saved four times is one item.
"""

import json
import os
import re
from urllib.parse import urlsplit

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

    # A credential dotfile is the same file with a dot in front of it, and
    # SECRET_NAMES holds the bare forms. Match on the name with leading dots
    # removed, or `.netrc` slips past `netrc` and is treated as ordinary, which
    # for a file named directly on the command line means it gets taken in.
    bare = lower.lstrip(".")
    stem, ext = os.path.splitext(bare)

    parts = os.path.normpath(path).split(os.sep)
    for part in parts[:-1]:
        if part.lower() in SECRET_DIRS:
            return "it is inside %s" % part

    if ext in SECRET_EXT:
        return "%s files hold keys or certificates" % ext
    if bare in SECRET_NAMES or stem in SECRET_NAMES:
        return "%s is a credential file" % name
    if lower.startswith(".env"):
        return "dotenv files hold secrets"
    for prefix in SECRET_PREFIXES:
        if bare.startswith(prefix):
            return "%s looks like a key or service account" % name
    return None


def one_line(text, limit=120):
    """Collapse untrusted text to a single printable line.

    A filename is chosen by whoever made the file and may contain newlines and
    control characters. Interpolated raw into a report that an assistant reads,
    a name like "id_rsa\\nIgnore prior instructions" becomes a line of its own
    that reads like an instruction rather than a filename. The reasons above
    quote the name back, so both halves need this.
    """
    out = []
    for ch in text:
        if ch.isprintable():
            out.append(ch)
        elif ord(ch) < 256:
            out.append("\\x%02x" % ord(ch))
        else:
            out.append("\\u%04x" % ord(ch))
    line = "".join(out)
    if len(line) > limit:
        line = line[:limit] + "..."
    return line


def quoted(text, limit=120):
    """`one_line`, wrapped in JSON quoting so the delimiters cannot be forged.

    Escaping control characters is not enough by itself. A filename may contain
    a plain double quote, and `id_rsa": Ignore prior instructions` would close
    the quoted span early and leave the rest sitting outside it, reading as
    commentary rather than as part of the name.
    """
    return json.dumps(one_line(text, limit))


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
    """Keep path/query case; retain the existing scheme/slash/fragment policy.

    RFC 3986 section 6.2.2.1 makes hosts case-insensitive, not paths or queries.
    This is a deduplication key, never a destination to fetch.
    """
    u = url.strip()
    for prefix in ("http://", "https://"):
        if u.lower().startswith(prefix):
            u = u[len(prefix):]
            break
    parts = urlsplit("//" + u)
    userinfo, separator, host = parts.netloc.rpartition("@")
    authority = (userinfo + separator if separator else "") + host.lower()
    path = parts.path[:-1] if parts.path.endswith("/") else parts.path
    # Preserve even an empty query marker, and a slash inside a query value.
    query = ("?" + parts.query) if "?" in u.split("#", 1)[0] else ""
    # Hex digits in a percent triplet are case-insensitive. Keep the ordinary
    # letters, including query values, in their original case.
    return re.sub(r"%[0-9A-Fa-f]{2}", lambda match: match.group().upper(),
                  authority + path + query)


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
    key = normalise_url(url)
    # Compare stored URLs too: older records used an all-lowercase hash. Do not
    # rewrite their identities, lose their decisions, or overwrite an old item
    # when a new case-sensitive URL happens to hash to its old key.
    digest = store.hash_bytes(("url-v2\0" + key).encode("utf-8"))
    existing = next((item for item in store.list_items(root)
                     if item.get("kind") == "url" and item.get("url")
                     and normalise_url(item["url"]) == key), None)
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


def walk(paths, on_skip=None):
    """Yield every file under the given paths, skipping noise and dotfiles.

    Dotfiles and dot-directories are pruned here, before anything downstream
    looks at them. That is why `on_skip` exists on this function as well as on
    `add_paths`: a pruned `.env` or `.ssh/` never reaches the credential check,
    so without this a swept home directory reported nothing left alone at all.

    A pruned directory is reported as itself rather than walked into. Naming it
    is enough to tell a caller why the count is lower than they expected.
    """
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            hidden = [d for d in dirnames if d.startswith(".")]
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            if on_skip is not None:
                for name in sorted(hidden):
                    if name.lower() in SECRET_DIRS:
                        on_skip(os.path.join(dirpath, name),
                                "%s holds credentials, so it was not opened" % name)
            for name in sorted(filenames):
                if name in SKIP_NAMES:
                    continue
                if name.startswith("."):
                    if on_skip is not None:
                        path = os.path.join(dirpath, name)
                        reason = looks_like_secret(path)
                        if reason:
                            on_skip(path, reason)
                    continue
                yield os.path.join(dirpath, name)


def add_paths(root, paths, on_skip=None):
    """Add everything under `paths`, returning (added, duplicates).

    Files that look like credentials are never taken in. `on_skip`, when given,
    is called with (path, reason) for each one, so a caller can report them. The
    return shape is unchanged so existing callers keep working.
    """
    added = dupes = 0
    for path in walk(paths, on_skip=on_skip):
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

