"""MCP tool hints must match what each tool does. ChatGPT review rejects a tool
whose readOnly/destructive/openWorld hints disagree with its behaviour."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import mcp, store

# (readOnlyHint, destructiveHint). Destructive means it can overwrite something
# the person or their assistant recorded earlier.
EXPECTED = {
    "cyft_status": (True, False),
    "cyft_profile": (True, False),
    "cyft_set_goal": (False, True),
    "cyft_set_constraints": (False, True),
    "cyft_add": (False, False),
    "cyft_next_unread": (True, False),
    "cyft_record_reading": (False, True),
    "cyft_next_undecided": (True, False),
    "cyft_decide": (False, True),
    "cyft_confirm": (False, True),
    "cyft_digest": (True, False),
    "cyft_digest_mark": (False, False),
}


class Annotations(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cyft-hints-")
        store.ensure(self.root)
        store.save_profile(self.root, {"goals": [{"id": "g1", "name": "Ship"}],
                                       "constraints": {}})

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def call(self, name, args=None):
        return mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": args or {}}},
                          self.root)["result"]

    def snapshot(self):
        out = {}
        for base, _, files in os.walk(self.root):
            for name in files:
                with open(os.path.join(base, name), "rb") as fh:
                    out[os.path.join(base, name)] = fh.read()
        return out

    def test_every_tool_declares_all_three_hints(self):
        self.assertEqual(set(EXPECTED), set(t["name"] for t in mcp.public_tools()))
        for spec in mcp.public_tools():
            hints = spec.get("annotations") or {}
            for key in ("readOnlyHint", "destructiveHint", "openWorldHint"):
                self.assertIsInstance(hints.get(key), bool, (spec["name"], key))
            self.assertEqual((hints["readOnlyHint"], hints["destructiveHint"]),
                             EXPECTED[spec["name"]], spec["name"])
            # No tool reaches outside the store. Links are kept as text, never fetched.
            self.assertFalse(hints["openWorldHint"], spec["name"])
            if hints["readOnlyHint"]:
                self.assertFalse(hints["destructiveHint"], spec["name"])

    def test_tools_marked_read_only_write_nothing(self):
        self.call("cyft_add", {"targets": ["https://example.com/a", "https://example.com/b"]})
        first = store.list_items(self.root)[0]["id"]
        self.call("cyft_record_reading", {"item_id": first, "what": "A"})
        before = self.snapshot()
        for name, (read_only, _) in sorted(EXPECTED.items()):
            if read_only:
                self.assertFalse(self.call(name)["isError"], name)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
