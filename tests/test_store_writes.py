"""Regressions for overlapping whole-record writes and failed serialization."""

import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from cyft import store


class TestStoreWrites(unittest.TestCase):
    def test_overlapping_writers_each_replace_their_own_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "record.json")
            barrier = threading.Barrier(2)
            real_replace = os.replace
            errors = []
            temps = []

            def overlap(src, dst):
                temps.append(src)
                barrier.wait(timeout=5)
                real_replace(src, dst)

            def write(value):
                try:
                    store.write_json(path, value)
                except Exception as exc:
                    errors.append(exc)

            values = [{"writer": "a", "text": "a" * 50000},
                      {"writer": "b", "text": "b" * 50000}]
            with mock.patch.object(store.os, "replace", side_effect=overlap):
                threads = [threading.Thread(target=write, args=(v,)) for v in values]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)
                self.assertFalse(any(t.is_alive() for t in threads))
            self.assertEqual(errors, [])
            self.assertEqual(len(set(temps)), 2)
            self.assertIn(store.read_json(path), values)
            self.assertEqual(os.listdir(root), ["record.json"])

    def test_serialization_failure_keeps_old_record_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "record.json")
            store.write_json(path, {"old": True})
            with self.assertRaises(TypeError):
                store.write_json(path, {"unsupported": object()})
            self.assertEqual(store.read_json(path), {"old": True})
            self.assertEqual(os.listdir(root), ["record.json"])

    def test_replace_failure_keeps_old_record_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "record.json")
            store.write_json(path, {"old": True})
            with mock.patch.object(store.os, "replace", side_effect=OSError("refused")):
                with self.assertRaises(OSError):
                    store.write_json(path, {"new": True})
            self.assertEqual(store.read_json(path), {"old": True})
            self.assertEqual(os.listdir(root), ["record.json"])

    @unittest.skipUnless(os.name == "posix", "POSIX file permissions")
    def test_new_records_are_private(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "record.json")
            store.write_json(path, {"private": True})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
