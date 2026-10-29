"""A user can take their data out, and can wipe it, and a hosted root per user is path-safe."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyft import cli, intake, store

PROFILE = {"goals": [{"id": "g1", "name": "Ship it"}], "constraints": {}}


class ExportAndForget(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cyft-export-")
        self.root = os.path.join(self.tmp, "store")
        store.ensure(self.root)
        store.save_profile(self.root, PROFILE)
        with open(os.path.join(self.root, "config.json"), "w") as fh:
            json.dump({"preset": "xai", "api_key_env": "XAI_API_KEY"}, fh)
        intake.add_text(self.root, "a note worth keeping", "note")
        store.save_state(self.root, {"seq": 3, "digest_seq": 1})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_export_holds_every_user_file_and_no_settings(self):
        dest = os.path.join(self.tmp, "out.zip")
        store.export(self.root, dest)
        with zipfile.ZipFile(dest) as zf:
            names = set(zf.namelist())
            self.assertIn("profile.json", names)
            self.assertIn("state.json", names)
            items = [n for n in names if n.startswith("items/") and n.endswith("item.json")]
            self.assertEqual(len(items), 1)
            self.assertNotIn("config.json", names)
            self.assertNotIn(".lock", names)
            self.assertEqual(json.loads(zf.read("profile.json")), PROFILE)

    def test_failed_export_leaves_no_partial_zip(self):
        dest = os.path.join(self.tmp, "broken.zip")
        with mock.patch.object(zipfile.ZipFile, "write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                store.export(self.root, dest)
        self.assertFalse(os.path.exists(dest))

    def test_export_does_not_follow_a_symlinked_folder_out_of_the_store(self):
        outside = os.path.join(self.tmp, "outside")
        os.makedirs(outside)
        with open(os.path.join(outside, "secret.txt"), "w") as fh:
            fh.write("not the user's")
        shutil.rmtree(os.path.join(self.root, store.DIGESTS))
        os.symlink(outside, os.path.join(self.root, store.DIGESTS))
        dest = os.path.join(self.tmp, "out.zip")
        store.export(self.root, dest)
        with zipfile.ZipFile(dest) as zf:
            self.assertFalse(any("secret" in n for n in zf.namelist()))

    def test_export_refuses_to_write_inside_the_store(self):
        with self.assertRaises(ValueError):
            store.export(self.root, os.path.join(self.root, "items", "x.zip"))

    def test_forget_removes_user_data_and_keeps_settings(self):
        store.forget(self.root)
        self.assertEqual(store.list_items(self.root), [])
        self.assertIsNone(store.load_profile(self.root))
        self.assertEqual(store.load_state(self.root), {"last_digest": None})
        self.assertEqual(os.listdir(os.path.join(self.root, store.DIGESTS)), [])
        self.assertTrue(os.path.exists(os.path.join(self.root, "config.json")))

    def test_cli_forget_needs_yes(self):
        with mock.patch.object(cli, "err"), mock.patch.object(cli, "out"):
            code = cli.main(["--root", self.root, "forget"])
        self.assertNotEqual(code, 0)
        self.assertEqual(len(store.list_items(self.root)), 1)
        with mock.patch.object(cli, "out"):
            self.assertEqual(cli.main(["--root", self.root, "forget", "--yes"]), 0)
        self.assertEqual(store.list_items(self.root), [])

    def test_cli_export_writes_a_zip(self):
        dest = os.path.join(self.tmp, "cli.zip")
        with mock.patch.object(cli, "out"):
            self.assertEqual(cli.main(["--root", self.root, "export", dest]), 0)
        self.assertTrue(zipfile.is_zipfile(dest))

    def test_cli_export_will_not_overwrite(self):
        dest = os.path.join(self.tmp, "taken.zip")
        with open(dest, "w") as fh:
            fh.write("keep me")
        with mock.patch.object(cli, "err"), mock.patch.object(cli, "out"):
            self.assertNotEqual(cli.main(["--root", self.root, "export", dest]), 0)
        with open(dest) as fh:
            self.assertEqual(fh.read(), "keep me")


class UserRoot(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="cyft-users-")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_hostile_subjects_stay_inside_the_base(self):
        for subject in ("../../etc", "/abs", "a/b", "..", "user\0x", "C:\\x", "é"):
            root = store.user_root(self.base, subject)
            self.assertEqual(os.path.dirname(os.path.dirname(root)), self.base)
            self.assertNotIn(subject, root)

    def test_same_subject_same_root_different_subject_different_root(self):
        self.assertEqual(store.user_root(self.base, "u1"), store.user_root(self.base, "u1"))
        self.assertNotEqual(store.user_root(self.base, "u1"), store.user_root(self.base, "u2"))

    def test_issuer_separates_identical_subjects(self):
        self.assertNotEqual(store.user_root(self.base, "u1", issuer="https://a"),
                            store.user_root(self.base, "u1", issuer="https://b"))

    def test_separator_inside_a_claim_cannot_collide_two_users(self):
        self.assertNotEqual(store.user_root(self.base, "c", issuer="a\0b"),
                            store.user_root(self.base, "b\0c", issuer="a"))

    def test_unpaired_surrogate_subject_still_gets_a_root(self):
        self.assertTrue(store.user_root(self.base, "u\ud800"))

    def test_empty_or_non_string_subject_is_refused(self):
        for bad in ("", None, 5, b"u1"):
            with self.assertRaises(ValueError):
                store.user_root(self.base, bad)


if __name__ == "__main__":
    unittest.main()
