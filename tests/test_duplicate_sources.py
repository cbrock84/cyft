"""A duplicate keeps where it came from, not only a count."""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import intake, store


class DuplicateSources(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cyft-dups-")
        self.src = tempfile.mkdtemp(prefix="cyft-src-")
        store.ensure(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.src, ignore_errors=True)

    def file(self, name, data=b"same bytes"):
        path = os.path.join(self.src, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def names(self):
        (item,) = store.list_items(self.root)
        return [s["name"] for s in item["sources"]], item["seen"]

    def test_same_file_under_two_names_keeps_both_names(self):
        intake.add_paths(self.root, [self.file("from-phone.txt")])
        intake.add_paths(self.root, [self.file("from-laptop.txt")])
        self.assertEqual(self.names(), (["from-phone.txt", "from-laptop.txt"], 2))

    def test_url_variants_keep_each_spelling(self):
        intake.add_url(self.root, "https://Example.com/tool/")
        intake.add_url(self.root, "https://example.com/tool")
        self.assertEqual(self.names(),
                         (["https://Example.com/tool/", "https://example.com/tool"], 2))

    def test_identical_resubmission_counts_but_does_not_repeat_the_source(self):
        intake.add_url(self.root, "https://example.com/tool")
        intake.add_url(self.root, "https://example.com/tool")
        self.assertEqual(self.names(), (["https://example.com/tool"], 2))

    def test_item_saved_before_sources_existed_keeps_its_first_name(self):
        intake.add_url(self.root, "https://example.com/tool")
        (item,) = store.list_items(self.root)
        del item["sources"]
        store.save_item(self.root, item)
        intake.add_url(self.root, "https://example.com/tool/")
        self.assertEqual(self.names()[0],
                         ["https://example.com/tool", "https://example.com/tool/"])

    def test_source_list_is_bounded(self):
        with mock.patch.object(intake, "MAX_SOURCES", 3):
            for n in range(6):
                intake.add_paths(self.root, [self.file("copy-%d.txt" % n)])
        names, seen = self.names()
        self.assertEqual(seen, 6)
        self.assertEqual(names, ["copy-0.txt", "copy-1.txt", "copy-2.txt"])


if __name__ == "__main__":
    unittest.main()
