import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gmail" / "prepare_jobs.py"
SPEC = importlib.util.spec_from_file_location("prepare_jobs", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PrepareJobsTests(unittest.TestCase):
    def test_coherence_accepts_matching_mail1_fields(self):
        coherent, reason = MODULE.is_mail1_coherent(
            {
                "Mail1_Greeting_Name": "Alex",
                "Mail1_Hook": "I enjoyed your recent AI video.",
                "Mail1_Subject": "Quick collaboration idea",
                "Mail1_Content V1": "Hi Alex,\n\nI enjoyed your recent AI video.\nWould you be open to chatting?",
            }
        )
        self.assertTrue(coherent, reason)

    def test_coherence_rejects_wrong_greeting(self):
        coherent, reason = MODULE.is_mail1_coherent(
            {
                "Mail1_Greeting_Name": "Alex",
                "Mail1_Hook": "Hello",
                "Mail1_Subject": "Subject",
                "Mail1_Content V1": "Hi Sam,\n\nHello",
            }
        )
        self.assertFalse(coherent)
        self.assertTrue(reason.startswith("greeting_mismatch:"), reason)


if __name__ == "__main__":
    unittest.main()
