import csv
import json
from pathlib import Path
import tempfile
import unittest
from prepare_tum_csv import DatasetError, digest, inspect_csv, prepare, split_exact_csv


class LosslessCsvTests(unittest.TestCase):
    def test_parts_reconstruct_every_byte_and_preview_is_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "T1_LFP.txt"
            raw = "Time [s],Temperature [°C]\r\n-0.010,25.00000001\r\n0.000,26.10\r\n0.010,27\r\n0.020,28.000\r\n".encode()
            source.write_bytes(raw)
            parts, verification = split_exact_csv(source, root / "out/lfp/cell_temperatures", "lfp_t1", 65, 2)
            self.assertGreater(len(parts), 1)
            rebuilt = b""
            for i, part in enumerate(parts):
                data = part["path"].read_bytes().splitlines(keepends=True)
                rebuilt += b"".join(data if i == 0 else data[1:])
                self.assertLessEqual(part["bytes"], 65)
            self.assertEqual(rebuilt, raw)
            self.assertEqual(verification["source_reconstructed_sha256"], digest(source))
            self.assertEqual([(p["row_start"], p["row_end"]) for p in parts], [(1, 2), (3, 4)])
            preview = verification["preview_path"].read_bytes()
            self.assertEqual(preview, b"".join(raw.splitlines(keepends=True)[:3]))
            self.assertEqual(source.read_bytes(), raw)

    def test_single_part_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "U1_LFP.txt"
            source.write_bytes(b"Time [s],Voltage [V]\r\n-0.1,-0.00300\r\n0.1,0\r\n")
            parts, verification = split_exact_csv(source, root / "out/lfp/cell_voltages", "lfp_u1", 1000)
            self.assertEqual(len(parts), 1)
            self.assertEqual(parts[0]["path"].read_bytes(), source.read_bytes())

    def test_unknown_schema_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "T1_LFP.txt"
            path.write_text("timestamp,unexplained\n0,1\n")
            with self.assertRaisesRegex(DatasetError, "Unknown CSV schema"):
                inspect_csv(path)

    def test_nmc_surface_has_83_measurement_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "T_surf_NMC811.txt"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Time [s]"] + [f"Temperature {i} [°C]" for i in range(1, 84)])
                writer.writerow([0] + [25] * 83)
            self.assertEqual(inspect_csv(path, True)["measurement_channels"], 83)

    def test_unknown_license_blocks_data_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            license_file = root / "license.json"
            license_file.write_text(json.dumps({"license_spdx": "UNKNOWN"}))
            with self.assertRaisesRegex(DatasetError, "Unknown/unverified redistribution license"):
                prepare(root / "source", root / "output", license_file)
            self.assertFalse((root / "output").exists())

    def test_overlarge_single_row_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_bytes(b"time,value\n0," + b"1" * 100 + b"\n")
            with self.assertRaisesRegex(DatasetError, "single data row exceeds"):
                split_exact_csv(source, root / "out/lfp/group", "test", 50)


if __name__ == "__main__":
    unittest.main()
