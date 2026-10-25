import shutil
import subprocess
import unittest
from pathlib import Path


class FrontendTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is optional; needed only for the JS regression check")
    def test_http_startup_without_random_uuid(self):
        result = subprocess.run([shutil.which("node"), str(Path(__file__).with_name("frontend_crypto.cjs"))], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
