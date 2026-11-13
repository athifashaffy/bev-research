"""Tests for run_with_proof.py (AI-assisted). Uses temporary folders only."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from run_with_proof import main, sha256


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        Path("input.csv").write_text("a,b\n1,2\n")
        Path("make.py").write_text(
            "import sys, pathlib\nout = pathlib.Path(sys.argv[1]); out.mkdir()\n"
            "(out / 'fig.txt').write_text(open('input.csv').read().upper())\n")

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def run_tool(self):
        return main(["--output", "out", "--script", "make.py", "--input", "input.csv",
                     "--", sys.executable, "make.py", "out"])

    def test_record_contains_hashes_of_every_file(self):
        self.assertEqual(self.run_tool(), 0)
        record = json.loads(Path("out/PROOF.json").read_text())
        self.assertEqual(record["inputs"][0]["sha256"], sha256(Path("input.csv")))
        self.assertEqual(record["scripts"][0]["sha256"], sha256(Path("make.py")))
        self.assertEqual([o["path"] for o in record["outputs"]], ["out/fig.txt"])
        self.assertTrue(Path("out/PROOF.md").is_file())

    def test_verify_passes_then_detects_change(self):
        self.run_tool()
        self.assertEqual(main(["--verify", "out/PROOF.json"]), 0)
        Path("out/fig.txt").write_text("edited by hand")
        self.assertEqual(main(["--verify", "out/PROOF.json"]), 1)

    def test_verify_detects_extra_output(self):
        self.run_tool()
        Path("out/added.png").write_text("not from the script")
        self.assertEqual(main(["--verify", "out/PROOF.json"]), 1)

    def test_existing_output_folder_refused(self):
        Path("out").mkdir()
        with self.assertRaises(SystemExit):
            self.run_tool()


if __name__ == "__main__":
    unittest.main()
