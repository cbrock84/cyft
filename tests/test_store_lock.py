"""Concurrent writers through the MCP tools must not lose each other's updates."""

import multiprocessing
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import mcp, reading, store


def _add_same_url(root, times):
    for _ in range(times):
        mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "cyft_add",
                               "arguments": {"targets": ["https://example.com/x"]}}}, root)


class ConcurrentWrites(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cyft-lock-")
        store.ensure(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_parallel_adds_of_one_url_count_every_sighting(self):
        workers, each = 4, 25
        ctx = multiprocessing.get_context("spawn" if sys.platform == "win32" else "fork")
        procs = [ctx.Process(target=_add_same_url, args=(self.root, each))
                 for _ in range(workers)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(60)
            self.assertEqual(p.exitcode, 0)
        items = store.list_items(self.root)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["seen"], workers * each)

    def test_lock_is_reentrant_within_one_thread(self):
        with store.locked(self.root):
            with store.locked(self.root):
                store.save_state(self.root, {"last_digest": None})
        with store.locked(self.root):
            pass

    def test_slow_reading_keeps_a_decision_made_meanwhile(self):
        stale = {"id": "abc", "status": "new", "kind": "text", "text": "x", "name": "x"}
        store.save_item(self.root, dict(stale, status="decided", route="watch",
                                        decided_at="2026-10-27T00:00:00Z"))

        class Provider(object):
            def complete(self, *args):
                return '{"what": "A thing", "claims": []}'

        reading.read_item(self.root, {}, dict(stale), provider=Provider())
        saved = store.list_items(self.root)[0]
        self.assertEqual((saved["status"], saved["route"]), ("decided", "watch"))
        self.assertEqual(saved["what"], "A thing")


if __name__ == "__main__":
    unittest.main()
