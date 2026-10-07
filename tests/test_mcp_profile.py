"""Profile edits through the public MCP tool dispatch."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import mcp, store


class ProfileTools(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        store.ensure(self.root)
        store.save_profile(self.root, {
            "goals": [{"id": "goal-1", "name": "", "why": "", "stop_when": ""}],
            "constraints": {"can_buy": "No subscriptions", "custom": "keep me"},
        })

    def tearDown(self):
        self.temp.cleanup()

    def call(self, name, arguments):
        response = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": name, "arguments": arguments}}, self.root)
        return response["result"]

    def test_create_then_edit_preserves_existing_id_and_constraints(self):
        self.assertFalse(self.call("cyft_set_goal", {"name": "Ship prototype",
                                                      "why": "Validate demand"})["isError"])
        profile = store.load_profile(self.root)
        self.assertEqual(profile["goals"][0]["id"], "goal-1")
        self.assertEqual(profile["goals"][0]["why"], "Validate demand")
        self.assertFalse(self.call("cyft_set_goal", {"goal_id": "goal-1",
                                                      "name": "Ship beta",
                                                      "stop_when": "No users"})["isError"])
        goal = store.load_profile(self.root)["goals"][0]
        self.assertEqual((goal["id"], goal["why"], goal["stop_when"]),
                         ("goal-1", "Validate demand", "No users"))
        self.assertFalse(self.call("cyft_set_goal", {"name": "Find partners"})["isError"])
        self.assertEqual(len(store.load_profile(self.root)["goals"]), 2)

    def test_edit_keeps_decision_reference_and_constraints_keep_other_fields(self):
        store.save_item(self.root, {"id": "item1", "status": "decided", "goal": "goal-1"})
        self.call("cyft_set_goal", {"goal_id": "goal-1", "name": "Launch"})
        self.assertEqual(store.list_items(self.root)[0]["goal"], "goal-1")
        self.assertFalse(self.call("cyft_set_constraints", {"notes": "Weekends only"})["isError"])
        self.assertEqual(store.load_profile(self.root)["constraints"], {
            "can_buy": "No subscriptions", "custom": "keep me", "notes": "Weekends only"})

    def test_invalid_requests_do_not_change_file(self):
        path = os.path.join(self.root, "profile.json")
        with open(path, "rb") as fh:
            before = fh.read()
        for tool, args in (("cyft_set_goal", {"goal_id": "unknown", "name": "X"}),
                           ("cyft_set_goal", {"name": " "}),
                           ("cyft_set_constraints", {"can_buy": 42}),
                           ("cyft_set_constraints", {})):
            self.assertTrue(self.call(tool, args)["isError"])
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), before)

    def test_missing_or_malformed_profile_does_not_get_replaced(self):
        os.unlink(os.path.join(self.root, "profile.json"))
        self.assertTrue(self.call("cyft_set_goal", {"name": "X"})["isError"])
        store.save_profile(self.root, {"goals": "broken", "constraints": {}})
        self.assertTrue(self.call("cyft_set_constraints", {"notes": "X"})["isError"])
        self.assertEqual(store.load_profile(self.root)["goals"], "broken")


if __name__ == "__main__":
    unittest.main()
