import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "agent")]

from scripts.discover_apps import merge_config, proposed_aliases, safe_candidate
from tools.apps import AppNotApproved, open_application
from core.quick_commands import parse_launch


class AppDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.exe = self.root / "idea64.exe"
        self.exe.write_bytes(b"test fixture, never executed")

    def tearDown(self):
        self.temporary.cleanup()

    def test_verified_no_argument_app_gets_natural_alias(self):
        aliases = proposed_aliases([{"name": "IntelliJ IDEA 2026.2.3", "target": str(self.exe), "arguments": ""}])
        self.assertEqual(aliases["intellij"], [str(self.exe.resolve())])
        self.assertEqual(aliases["intellij idea"], [str(self.exe.resolve())])

    def test_arguments_scripts_installers_and_missing_targets_are_excluded(self):
        for record in [
            {"name": "IDE", "target": str(self.exe), "arguments": "--execute malicious"},
            {"name": "Uninstall IDE", "target": str(self.exe), "arguments": ""},
            {"name": "IDE", "target": str(self.root / "missing.exe"), "arguments": ""},
            {"name": "Script", "target": str(self.root / "launch.cmd"), "arguments": ""},
            {"name": "IDE", "target": "relative.exe", "arguments": ""},
            {"name": "IDE", "target": "\\\\network\\share\\app.exe", "arguments": ""},
        ]:
            self.assertIsNone(safe_candidate(record), record)

    def test_ambiguous_installations_do_not_get_shared_alias(self):
        second = self.root / "other.exe"
        second.write_bytes(b"fixture")
        aliases = proposed_aliases([
            {"name": "IntelliJ IDEA 2026", "target": str(self.exe)},
            {"name": "IntelliJ IDEA 2025", "target": str(second)},
        ])
        self.assertNotIn("intellij", aliases)
        self.assertIn("intellij idea 2026", aliases)

    def test_merge_preserves_roots_and_existing_approval(self):
        config = {"permissions": {"approved_search_roots": ["D:/"], "approved_app_allowlist": {"intellij": ["original.exe"]}}, "custom": {"keep": True}}
        updated, added = merge_config(config, {"intellij": [str(self.exe)], "postman": [str(self.exe)]})
        self.assertEqual(updated["permissions"]["approved_search_roots"], ["D:/"])
        self.assertEqual(updated["permissions"]["approved_app_allowlist"]["intellij"], ["original.exe"])
        self.assertEqual(updated["custom"], config["custom"])
        self.assertEqual(set(added), {"postman"})
        self.assertNotIn("postman", config["permissions"]["approved_app_allowlist"])

    def test_unknown_app_cannot_execute_process(self):
        with patch("tools.apps.approved_apps", return_value={"intellij": [str(self.exe)]}), \
             patch("tools.apps.subprocess.Popen") as launch:
            with self.assertRaises(AppNotApproved):
                open_application("unrelated imaginary application")
            launch.assert_not_called()

    def test_known_app_uses_fixed_shell_free_argv(self):
        with patch("tools.apps.approved_apps", return_value={"intellij": [str(self.exe)]}), \
             patch("tools.apps.platform.system", return_value="Windows"), \
             patch("tools.apps.public_environment", return_value={"PATH": "safe"}), \
             patch("tools.apps.subprocess.Popen") as launch:
            launch.return_value.pid = 123
            self.assertTrue(open_application("intellij")["launched"])
            launch.assert_called_once_with([str(self.exe)], shell=False, env={"PATH": "safe"})

    def test_new_apps_work_through_deterministic_multilingual_parser(self):
        with patch("core.quick_commands.approved_apps", return_value={"postman": [], "intellij": []}):
            self.assertEqual(parse_launch("पोस्टमैन खोलो"), ("open_application", {"name": "postman"}))
            self.assertEqual(parse_launch("open intellij"), ("open_application", {"name": "intellij"}))
            self.assertIsNone(parse_launch("open postman --execute command"))


if __name__ == "__main__":
    unittest.main()
