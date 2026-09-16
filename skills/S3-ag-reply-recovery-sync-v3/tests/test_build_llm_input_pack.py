import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_llm_input_pack.py"
SPEC = importlib.util.spec_from_file_location("build_llm_input_pack", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

PATH_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "project_paths.py"
PATH_SPEC = importlib.util.spec_from_file_location("project_paths", PATH_SCRIPT)
PATH_MODULE = importlib.util.module_from_spec(PATH_SPEC)
assert PATH_SPEC and PATH_SPEC.loader
PATH_SPEC.loader.exec_module(PATH_MODULE)


class BuildLlmInputPackTests(unittest.TestCase):
    def test_trusted_ocr_map_groups_case_insensitively(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "ocr.csv"
            csv_path.write_text(
                "from_email,price_raw\nCreator@One.Example.Invalid,\"$1,500\"\ncreator@one.example.invalid,\"$2,000\"\n",
                encoding="utf-8",
            )
            mapping = MODULE.build_trusted_ocr_map(csv_path)

        self.assertEqual(len(mapping["creator@one.example.invalid"]), 2)
        self.assertEqual(mapping["creator@one.example.invalid"][0]["price_raw"], "$1,500")

    def test_slug_is_file_safe(self):
        self.assertEqual(MODULE.slug("  Alex / Creator  "), "Alex-Creator")
        self.assertEqual(MODULE.slug(""), "unknown")

    def test_project_path_is_vault_location_independent(self):
        with tempfile.TemporaryDirectory(prefix="rockbase path ") as directory:
            with patch.dict(os.environ, {"ROCKBASE_PROJECT_ROOT": directory}, clear=False):
                root = Path(directory).resolve()
                self.assertEqual(PATH_MODULE.project_root(), root)
                self.assertEqual(PATH_MODULE.project_path("workbench"), root / "workbench")


if __name__ == "__main__":
    unittest.main()
