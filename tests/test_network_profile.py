"""The tool surface a networked server may expose: no local paths in, no server
paths out, and pasted text as an input that needs no file."""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import intake, mcp, store


class NetworkProfile(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cyft-net-")
        store.ensure(self.root)
        store.save_profile(self.root, {"goals": [{"id": "g1", "name": "Ship"}],
                                       "constraints": {}})
        fd, self.secret = tempfile.mkstemp(suffix=".txt")
        os.write(fd, b"server-side file that must never be read")
        os.close(fd)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        os.unlink(self.secret)

    def call(self, name, args=None, network=True, root=None):
        result = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": name, "arguments": args or {}}},
                            root or self.root, network=network)["result"]
        return result, " ".join(c.get("text", "") for c in result["content"])

    def test_local_paths_are_refused_and_nothing_is_read(self):
        for targets in ([self.secret], [os.path.dirname(self.secret)],
                        ["https://example.com/a", self.secret], ["file:///etc/passwd"]):
            result, text = self.call("cyft_add", {"targets": targets})
            self.assertTrue(result["isError"], targets)
            self.assertNotIn(self.secret, text)
        self.assertEqual(store.list_items(self.root), [])

    def test_links_and_pasted_text_still_work(self):
        result, text = self.call("cyft_add", {
            "targets": ["https://example.com/a"],
            "notes": [{"title": "Thread about a tool", "text": "Someone said X is great"}]})
        self.assertFalse(result["isError"], text)
        self.assertIn("2 added", text)
        kinds = sorted(i["kind"] for i in store.list_items(self.root))
        self.assertEqual(kinds, ["text", "url"])

    def test_local_mode_still_takes_paths(self):
        result, text = self.call("cyft_add", {"targets": [self.secret]}, network=False)
        self.assertFalse(result["isError"], text)

    def test_tool_list_does_not_offer_paths(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, self.root,
                       network=True)
        add = next(t for t in r["result"]["tools"] if t["name"] == "cyft_add")
        blob = json.dumps(add).lower()
        self.assertNotIn("path", blob)
        self.assertNotIn("folder", blob)
        local = next(t for t in mcp.public_tools() if t["name"] == "cyft_add")
        self.assertIn("path", json.dumps(local).lower())

    def test_no_reply_names_the_server_store_path(self):
        for name in ("cyft_status", "cyft_profile", "cyft_digest", "cyft_next_unread"):
            _, text = self.call(name)
            self.assertNotIn(self.root, text, name)
        os.unlink(os.path.join(self.root, "profile.json"))
        for name, args in (("cyft_profile", {}), ("cyft_set_goal", {"name": "X"})):
            result, text = self.call(name, args)
            self.assertTrue(result["isError"])
            self.assertNotIn(self.root, text, name)
        missing = os.path.join(self.root, "nope")
        _, text = self.call("cyft_add", {"targets": ["https://example.com"]}, root=missing)
        self.assertNotIn(missing, text)


class PastedText(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cyft-notes-")
        store.ensure(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def call(self, args):
        result = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "cyft_add", "arguments": args}},
                            self.root)["result"]
        return result, " ".join(c.get("text", "") for c in result["content"])

    def test_identical_notes_merge_and_keep_both_titles(self):
        self.call({"notes": [{"title": "From Slack", "text": "Try tool X"}]})
        _, text = self.call({"notes": [{"title": "From email", "text": "Try tool X"}]})
        self.assertIn("0 added, 1 already", text)
        (item,) = store.list_items(self.root)
        self.assertEqual(item["text"], "Try tool X")
        self.assertEqual([s["name"] for s in item["sources"]], ["From Slack", "From email"])

    def test_bad_notes_are_refused_whole(self):
        for notes in ("text", [{"text": ""}], [{"text": 3}], [{"title": 3, "text": "x"}],
                      [{"text": "x" * (intake.MAX_NOTE_CHARS + 1)}],
                      [{"text": "ok"}] * (mcp.MAX_NOTES + 1)):
            result, _ = self.call({"notes": notes})
            self.assertTrue(result["isError"], str(notes)[:60])
        self.assertEqual(store.list_items(self.root), [])

    def test_needs_targets_or_notes(self):
        self.assertTrue(self.call({})[0]["isError"])
        self.assertTrue(self.call({"targets": []})[0]["isError"])


if __name__ == "__main__":
    unittest.main()
