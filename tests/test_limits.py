"""Size limits are enforced and stated where the caller can see them."""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import intake, mcp, store

PNG = b"\x89PNG\r\n\x1a\n"


class Limits(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cyft-limits-")
        self.src = tempfile.mkdtemp(prefix="cyft-src-")
        store.ensure(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.src, ignore_errors=True)

    def call(self, name, args=None):
        result = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": name, "arguments": args or {}}},
                            self.root)["result"]
        return result, " ".join(c.get("text", "") for c in result["content"])

    def file(self, name, data):
        path = os.path.join(self.src, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_oversized_screenshot_is_not_inlined(self):
        path = self.file("big.png", PNG + b"\0" * 64)
        with mock.patch.object(mcp, "MAX_INLINE_IMAGE_BYTES", 32):
            self.call("cyft_add", {"targets": [path]})
            result, text = self.call("cyft_next_unread")
        self.assertFalse(result["isError"])
        self.assertNotIn("image", [c["type"] for c in result["content"]])
        self.assertIn("not attached", text)

    def test_small_screenshot_is_still_inlined(self):
        path = self.file("small.png", PNG)
        self.call("cyft_add", {"targets": [path]})
        result, _ = self.call("cyft_next_unread")
        self.assertIn("image", [c["type"] for c in result["content"]])

    def test_oversized_file_is_refused_and_named_not_as_a_credential(self):
        big = self.file("huge.txt", b"x" * 64)
        self.file("fine.txt", b"ok")
        with mock.patch.object(intake, "MAX_FILE_BYTES", 32):
            result, text = self.call("cyft_add", {"targets": [self.src]})
        self.assertFalse(result["isError"])
        self.assertIn("1 added", text)
        self.assertIn("huge.txt", text)
        self.assertIn("larger than", text)
        self.assertNotIn("look like credentials", text)
        self.assertEqual([i["name"] for i in store.list_items(self.root)], ["fine.txt"])
        self.assertTrue(os.path.exists(big))

    def test_limits_are_stated_in_tool_descriptions(self):
        tools = dict((t["name"], t["description"]) for t in mcp.public_tools())
        self.assertIn("MB", tools["cyft_add"])
        self.assertIn("characters", tools["cyft_add"])
        self.assertIn("MB", tools["cyft_next_unread"])
        self.assertIn("characters", tools["cyft_next_unread"])


if __name__ == "__main__":
    unittest.main()
