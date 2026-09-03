"""Best-effort PDF text extraction, with no dependencies.

This handles the common case: a PDF whose pages carry text in Flate-compressed
content streams. It does not handle scanned pages, which contain no text at all,
and it will not always survive unusual font encodings.

That is why every extraction is graded before it is used. A PDF that yields
garbage is reported as unreadable rather than passed on as if it were text,
because feeding noise to the reading stage is worse than admitting the gap.
"""

import re
import zlib

# Text-showing operators. Tj and ' take one string; TJ takes an array of strings
# and kerning numbers; " takes two numbers then a string.
_TEXT_OPS = re.compile(rb"(\((?:\\.|[^\\()])*\)|\[(?:[^\[\]\\]|\\.)*\])\s*(TJ|Tj|'|\")")
_STRING = re.compile(rb"\((?:\\.|[^\\()])*\)")

_ESCAPES = {
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"b": b"\x08",
    b"f": b"\x0c",
    b"(": b"(",
    b")": b")",
    b"\\": b"\\",
}


def _unescape(raw):
    """Resolve PDF string escapes, including octal character codes."""
    out = bytearray()
    i, n = 0, len(raw)
    while i < n:
        c = raw[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        nxt = raw[i + 1:i + 2]
        if nxt in _ESCAPES:
            out += _ESCAPES[nxt]
            i += 2
        elif nxt.isdigit():
            digits = b""
            j = i + 1
            while j < n and len(digits) < 3 and raw[j:j + 1].isdigit():
                digits += raw[j:j + 1]
                j += 1
            try:
                out.append(int(digits, 8) & 0xFF)
            except ValueError:
                pass
            i = j
        elif nxt == b"\n":
            i += 2                      # line continuation, emits nothing
        else:
            out += nxt
            i += 2
    return bytes(out)


def _streams(data):
    """Yield each decompressed content stream we can get at."""
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        blob = data[start:end]
        try:
            yield zlib.decompress(blob)
        except zlib.error:
            # Uncompressed, or a filter we do not implement. Only useful raw if
            # it actually looks like a content stream.
            if _TEXT_OPS.search(blob):
                yield blob


def _is_content(stream):
    """True for a stream that draws text, false for metadata and font blobs."""
    return b"BT" in stream and (b"Tj" in stream or b"TJ" in stream)


def _text_from_stream(stream):
    """Every string in a content stream, in order, with no separator inserted.

    Separators are deliberately not added between strings. A PDF splits words
    across strings for kerning, so joining with a space turns "December 18,
    2023" into two fragments. Real word spacing is already inside the strings.
    """
    return [_unescape(s[1:-1]) for s in _STRING.findall(stream)]


def looks_like_text(text, min_chars=40, min_printable=0.80, min_letters=0.35):
    """Grade an extraction. False means: do not pretend this is readable."""
    if not text or len(text) < min_chars:
        return False
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\t ")
    if printable / float(len(text)) < min_printable:
        return False
    letters = sum(1 for ch in text if ch.isalpha())
    return letters / float(len(text)) >= min_letters


def extract(data, limit=20000):
    """Return extracted text, or an empty string when nothing trustworthy came out."""
    parts = []
    total = 0
    for stream in _streams(data):
        if not _is_content(stream):
            continue
        for chunk in _text_from_stream(stream):
            parts.append(chunk)
            total += len(chunk)
        if total > limit * 3:
            break
    if not parts:
        return ""

    text = b"".join(parts).decode("latin-1", "replace")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = text.strip()
    if not looks_like_text(text):
        return ""
    return text[:limit]
