import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "feishu_s3_replyops_writeback.py"
SPEC = importlib.util.spec_from_file_location("feishu_s3_replyops_writeback", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FeishuNetworkDiagnosisTests(unittest.TestCase):
    def test_describe_network_context_includes_proxy_values(self) -> None:
        original_http = MODULE.os.environ.get("HTTP_PROXY")
        original_https = MODULE.os.environ.get("HTTPS_PROXY")
        try:
            MODULE.os.environ["HTTP_PROXY"] = "http://127.0.0.1:1082"
            MODULE.os.environ["HTTPS_PROXY"] = "http://127.0.0.1:1082"
            text = MODULE.describe_network_context()
        finally:
            if original_http is None:
                MODULE.os.environ.pop("HTTP_PROXY", None)
            else:
                MODULE.os.environ["HTTP_PROXY"] = original_http
            if original_https is None:
                MODULE.os.environ.pop("HTTPS_PROXY", None)
            else:
                MODULE.os.environ["HTTPS_PROXY"] = original_https

        self.assertIn("HTTP_PROXY=http://127.0.0.1:1082", text)
        self.assertIn("HTTPS_PROXY=http://127.0.0.1:1082", text)

    def test_wrap_request_error_adds_feishu_context(self) -> None:
        err = MODULE.requests.exceptions.ProxyError("proxy tunnel 503")
        wrapped = MODULE.wrap_request_error("tenant_access_token", err)
        self.assertIsInstance(wrapped, RuntimeError)
        message = str(wrapped)
        self.assertIn("Feishu API request failed during tenant_access_token", message)
        self.assertIn("ProxyError", message)
        self.assertIn("network_context=", message)


if __name__ == "__main__":
    unittest.main()
