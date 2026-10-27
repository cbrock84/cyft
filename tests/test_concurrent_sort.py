"""`cyft sort` waits on a person. Whatever MCP did meanwhile must survive."""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import cli, mcp, store

PROFILE = {"goals": [{"id": "g1", "name": "Ship"}], "constraints": {}}


class SortAgainstConcurrentMcp(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cyft-sort-")
        store.ensure(self.root)
        store.save_profile(self.root, PROFILE)
        self.call("cyft_add", {"targets": ["https://example.com/x"]})
        self.id = store.list_items(self.root)[0]["id"]
        self.call("cyft_record_reading", {"item_id": self.id, "what": "X"})

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def call(self, name, args):
        return mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": args}}, self.root)

    def sort(self, answers, during_route_prompt):
        answers = iter(answers)

        def ask(prompt):
            if "Route" in prompt:
                during_route_prompt()
            return next(answers)

        with mock.patch.object(cli, "_ask", side_effect=ask), \
                mock.patch.object(cli, "out"), mock.patch.object(cli, "err"):
            cli.main(["--root", self.root, "sort"])
        return store.list_items(self.root)[0]

    def test_proposal_confirmed_over_mcp_meanwhile_is_not_decided_twice(self):
        self.call("cyft_decide", {"item_id": self.id, "goal": "g1",
                                  "help": "lot", "cost": "hour"})
        item = self.sort(["watch"], lambda: self.call("cyft_confirm",
                                                      {"item_ids": [self.id]}))
        self.assertEqual((item["route"], item["decided_by"], item["decided_seq"]),
                         ("act", "person-via-mcp-client", 1))

    def test_reading_recorded_over_mcp_meanwhile_is_kept(self):
        claim = {"text": "It is fast", "label": "claimed"}
        item = self.sort(["1", "1", "1", "", ""], lambda: self.call(
            "cyft_record_reading", {"item_id": self.id, "what": "X, re-read",
                                    "claims": [claim]}))
        self.assertEqual(item["status"], "decided")
        self.assertEqual(item["what"], "X, re-read")
        self.assertEqual([c["text"] for c in item["claims"]], ["It is fast"])

    def test_record_reading_does_not_undo_a_decision(self):
        self.call("cyft_decide", {"item_id": self.id, "goal": "g1",
                                  "help": "lot", "cost": "hour"})
        self.call("cyft_confirm", {"item_ids": [self.id]})
        self.call("cyft_record_reading", {"item_id": self.id, "what": "X again"})
        item = store.list_items(self.root)[0]
        self.assertEqual((item["status"], item["what"]), ("decided", "X again"))


if __name__ == "__main__":
    unittest.main()
