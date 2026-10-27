"""The digest read marker is a change counter, not a wall-clock second."""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import mcp, store

PROFILE = {"goals": [{"id": "g1", "name": "Ship it"}], "constraints": {}}
FROZEN = "2026-10-27T03:00:00Z"


class DigestCursor(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cyft-digest-")
        store.ensure(self.root)
        store.save_profile(self.root, PROFILE)
        self.clock = mock.patch.object(store, "now", return_value=FROZEN)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def call(self, name, args=None):
        result = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": name, "arguments": args or {}}},
                            self.root)["result"]
        return result, " ".join(c.get("text", "") for c in result["content"])

    def decide(self, url):
        self.call("cyft_add", {"targets": [url]})
        item = next(i for i in store.list_items(self.root) if i["url"] == url)
        self.call("cyft_decide", {"item_id": item["id"], "goal": "g1",
                                  "help": "lot", "cost": "hour"})
        result, _ = self.call("cyft_confirm", {"item_ids": [item["id"]]})
        self.assertFalse(result["isError"])
        return item["id"]

    def cursor(self, text):
        marker = "cyft_digest_mark with through="
        self.assertIn(marker, text)
        return int(text.split(marker, 1)[1].split()[0].rstrip("."))

    def snapshot(self):
        out = {}
        for base, _, files in os.walk(self.root):
            for name in files:
                path = os.path.join(base, name)
                with open(path, "rb") as fh:
                    out[path] = fh.read()
        return out

    def test_decision_in_the_same_second_as_the_mark_is_not_lost(self):
        self.decide("https://example.com/first")
        _, text = self.call("cyft_digest")
        self.call("cyft_digest_mark", {"through": self.cursor(text)})
        self.decide("https://example.com/second")
        _, text = self.call("cyft_digest")
        self.assertIn("example.com/second", text)
        self.assertNotIn("example.com/first", text)

    def test_decision_between_render_and_mark_is_not_skipped(self):
        self.decide("https://example.com/first")
        _, text = self.call("cyft_digest")
        shown = self.cursor(text)
        self.decide("https://example.com/late")
        self.call("cyft_digest_mark", {"through": shown})
        _, text = self.call("cyft_digest")
        self.assertIn("example.com/late", text)
        self.assertNotIn("example.com/first", text)

    def test_reading_the_digest_writes_nothing(self):
        self.decide("https://example.com/first")
        before = self.snapshot()
        self.call("cyft_digest")
        self.call("cyft_digest", {"all": True})
        self.assertEqual(self.snapshot(), before)

    def test_mark_rejects_a_cursor_it_never_issued(self):
        self.decide("https://example.com/first")
        for bad in (99, -1, "1", True, None):
            result, _ = self.call("cyft_digest_mark", {"through": bad})
            self.assertTrue(result["isError"], bad)
        _, text = self.call("cyft_digest")
        self.assertIn("example.com/first", text)

    def test_mark_never_moves_backwards(self):
        self.decide("https://example.com/first")
        _, text = self.call("cyft_digest")
        self.call("cyft_digest_mark", {"through": self.cursor(text)})
        self.call("cyft_digest_mark", {"through": 0})
        _, text = self.call("cyft_digest")
        self.assertIn("Nothing new", text)

    def test_digest_mark_argument_is_refused_rather_than_silently_writing(self):
        self.decide("https://example.com/first")
        result, text = self.call("cyft_digest", {"mark": True})
        self.assertTrue(result["isError"])
        self.assertIn("cyft_digest_mark", text)

    def test_cli_mark_uses_the_same_counter(self):
        from cyft import cli
        self.decide("https://example.com/first")
        with mock.patch.object(cli, "out"):
            cli.main(["--root", self.root, "digest", "--mark"])
        self.decide("https://example.com/second")
        _, text = self.call("cyft_digest")
        self.assertIn("example.com/second", text)
        self.assertNotIn("example.com/first", text)


if __name__ == "__main__":
    unittest.main()
