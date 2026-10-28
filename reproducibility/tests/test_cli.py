"""Adversarial source-integrity tests; no simulation or model training."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib,json,unittest
from bev_research.cli import _relative,_new_output,_hashes
class IntegrityTests(unittest.TestCase):
    def test_relative_paths(self):
        self.assertEqual(_relative('workspace/a.csv').as_posix(),'workspace/a.csv')
        for path in ('../x','/etc/passwd','C:/x','workspace/../../x',''):
            with self.assertRaises(ValueError):_relative(path)
    def test_output_protection(self):
        with TemporaryDirectory() as t:
            root=Path(t);data=root/'data';data.mkdir()
            with self.assertRaises(ValueError):_new_output(data/'outputs',data)
            with self.assertRaises(ValueError):_new_output(data,data)
            _new_output(root/'new',data)
    def test_hash_match_and_tamper_failure(self):
        with TemporaryDirectory() as t:
            root=Path(t);data=root/'data';source=data/'workspace';source.mkdir(parents=True)
            f=source/'x.csv';f.write_bytes(b'a,b\n1,2\n')
            entry={'path':'workspace/x.csv','bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
            (data/'SOURCE_MANIFEST.json').write_text(json.dumps({'files':[entry]}))
            _hashes(source,root/'pass');f.write_bytes(b'a,b\n2,3\n')
            with self.assertRaises(ValueError):_hashes(source,root/'fail')
    def test_duplicate_manifest_rejected(self):
        with TemporaryDirectory() as t:
            root=Path(t);data=root/'data';source=data/'workspace';source.mkdir(parents=True)
            f=source/'x';f.write_bytes(b'x');entry={'path':'workspace/x','bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}
            (data/'SOURCE_MANIFEST.json').write_text(json.dumps([entry,entry]))
            with self.assertRaises(ValueError):_hashes(source,root/'out')
if __name__=='__main__':unittest.main()
