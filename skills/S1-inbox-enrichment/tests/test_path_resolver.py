import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "browser" / "internal" / "path_resolver.py"
SPEC = importlib.util.spec_from_file_location("path_resolver", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PathResolverTests(unittest.TestCase):
    def test_project_root_uses_environment_override(self):
        with tempfile.TemporaryDirectory(prefix="rockbase path ") as directory:
            with patch.dict(os.environ, {"ROCKBASE_PROJECT_ROOT": directory}, clear=False):
                self.assertEqual(MODULE.project_root(), Path(directory).resolve())

    def test_relative_csv_path_is_project_relative(self):
        with tempfile.TemporaryDirectory(prefix="rockbase path ") as directory:
            with patch.dict(os.environ, {"ROCKBASE_PROJECT_ROOT": directory}, clear=False):
                resolved = MODULE.resolve_csv_path("Agency/list-master/example.csv")
                self.assertEqual(resolved, Path(directory).resolve() / "Agency/list-master/example.csv")


if __name__ == "__main__":
    unittest.main()
