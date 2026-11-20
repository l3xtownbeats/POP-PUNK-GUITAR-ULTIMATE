import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_paths import APP_FOLDER_NAME, resolve_runtime_paths, resource_file


class RuntimePathTests(unittest.TestCase):
    def test_source_run_keeps_data_next_to_module(self):
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "manager_gui.py"
            module.touch()
            bundle, data, portable = resolve_runtime_paths(module, frozen=False)
            self.assertEqual(bundle, Path(directory))
            self.assertEqual(data, Path(directory))
            self.assertFalse(portable)

    def test_portable_run_uses_user_data_beside_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "Manager.exe"
            exe.touch()
            (Path(directory) / "portable.mode").touch()
            bundle, data, portable = resolve_runtime_paths(
                exe, executable=exe, frozen=True, environ={}
            )
            self.assertEqual(bundle, Path(directory))
            self.assertEqual(data, Path(directory) / "UserData")
            self.assertTrue(portable)

    def test_installed_run_uses_local_appdata_not_program_files(self):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "Program Files" / "Manager" / "Manager.exe"
            exe.parent.mkdir(parents=True)
            exe.touch()
            local = Path(directory) / "LocalAppData"
            bundle, data, portable = resolve_runtime_paths(
                exe, executable=exe, frozen=True,
                environ={"LOCALAPPDATA": str(local)}
            )
            self.assertEqual(bundle, exe.parent)
            self.assertEqual(data, local / APP_FOLDER_NAME)
            self.assertFalse(portable)
            self.assertNotEqual(data, bundle)

    def test_runtime_staging_root_uses_persistent_data_directory(self):
        from app_paths import runtime_staging_root
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "Manager.exe"
            exe.touch()
            (Path(directory) / "portable.mode").touch()
            with patch("app_paths.sys.frozen", True, create=True), \
                 patch("app_paths.sys.executable", str(exe)):
                self.assertEqual(runtime_staging_root(exe), Path(directory) / "UserData" / "staging")

    def test_resource_resolution_uses_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "manager_gui.py"
            module.touch()
            guide = Path(directory) / "PORTABLE_USER_GUIDE_RU.md"
            guide.write_text("guide", encoding="utf-8")
            self.assertEqual(resource_file(
                guide.name, module_file=module, bundle_dir=directory
            ), guide)


