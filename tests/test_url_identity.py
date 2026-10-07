"""URL deduplication must not discard case-sensitive resource identities."""

import tempfile
import unittest

from cyft import intake, store


class TestUrlIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = store.ensure(self.tmp.name)

    def test_path_case_stays_separate(self):
        for url in ("https://example.com/Guide", "https://example.com/guide"):
            self.assertTrue(intake.add_url(self.root, url)[1])
        self.assertEqual(len(store.list_items(self.root)), 2)

    def test_query_keys_and_values_keep_case(self):
        for url in ("https://example.com/?Token=AbC", "https://example.com/?Token=abc",
                    "https://example.com/?token=AbC"):
            self.assertTrue(intake.add_url(self.root, url)[1])
        self.assertEqual(len(store.list_items(self.root)), 3)

    def test_host_case_and_existing_alias_policy_still_merge(self):
        first, _ = intake.add_url(self.root, "https://EXAMPLE.com/Guide/")
        second, new = intake.add_url(self.root, "HTTP://example.com/Guide#section")
        self.assertFalse(new)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["seen"], 2)

    def test_slash_in_query_value_is_not_removed(self):
        self.assertNotEqual(intake.normalise_url("https://example.com/?next=Docs/"),
                            intake.normalise_url("https://example.com/?next=Docs"))

    def test_credentials_and_empty_query_keep_case_and_marker(self):
        self.assertEqual(intake.normalise_url("https://User:Pass@EXAMPLE.com/A?"),
                         "User:Pass@example.com/A?")

    def test_percent_triplet_hex_case_merges_without_lowering_other_text(self):
        first, _ = intake.add_url(self.root, "https://example.com/Guide%2fb?Token=%3a")
        second, is_new = intake.add_url(self.root, "https://EXAMPLE.com/Guide%2Fb?Token=%3A")
        self.assertFalse(is_new)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(intake.normalise_url(first["url"]),
                         "example.com/Guide%2Fb?Token=%3A")

    def test_invalid_percent_escape_is_not_interpreted(self):
        self.assertNotEqual(intake.normalise_url("https://example.com/%2g"),
                            intake.normalise_url("https://example.com/%2G"))

    def legacy_item(self, url):
        key = url.split("://", 1)[1].lower()
        digest = store.hash_bytes(key.encode("utf-8"))
        item = intake._blank_item(store.new_id(digest), digest, "url", url)
        item.update(url=url, status="decided", route="reference", reason="keep this")
        store.save_item(self.root, item)
        return item

    def test_legacy_mixed_case_item_is_reused_without_rewriting_identity(self):
        old = self.legacy_item("https://example.com/Guide")
        item, new = intake.add_url(self.root, "https://EXAMPLE.com/Guide#part")
        self.assertFalse(new)
        self.assertEqual(item["id"], old["id"])
        self.assertEqual(item["hash"], old["hash"])
        self.assertEqual(item["route"], "reference")
        self.assertEqual(item["seen"], 2)

    def test_new_lowercase_url_cannot_overwrite_legacy_mixed_case_item(self):
        old = self.legacy_item("https://example.com/Guide")
        item, new = intake.add_url(self.root, "https://example.com/guide")
        self.assertTrue(new)
        self.assertNotEqual(item["id"], old["id"])
        saved = store.read_json(store.item_path(self.root, old["id"]))
        self.assertEqual(saved, old)
        self.assertEqual(len(store.list_items(self.root)), 2)

