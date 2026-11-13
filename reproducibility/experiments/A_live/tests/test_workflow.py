"""AI-assisted output integrity and real model replay tests."""
from pathlib import Path
import sys,tempfile,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import train as trainer
from telemetry import generate,predict_history,build_examples,original
class WorkflowTests(unittest.TestCase):
    def test_output_rejects_existing_or_input_directory(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):trainer.validate_output(Path(d))
        with self.assertRaises(ValueError):trainer.validate_output(trainer.REPRO/"data/new-result")

    def test_saved_model_replay_is_same_as_batch_prediction(self):
        import joblib
        events=[dict(start_s=0,end_s=500,energy_kwh=20)]
        s=generate(events,354,500);e=build_examples(s,354,3,60)
        model=original.estimator("hist_gradient_boosting",{"max_iter":40})
        model.fit(e['x'],e['delta_c'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model.joblib';joblib.dump(model,p);restored=joblib.load(p)
            got=predict_history(s[:61],354,3,{60:restored})[60]['hist_gradient_boosting']
            self.assertEqual(got,float(e['x'][0,0]+model.predict(e['x'][:1])[0]))

    def test_proof_detects_changed_output(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);f=p/'data.txt';f.write_text('original')
            trainer.write_json(p/'status.json',{'state':'COMPLETE'})
            trainer.write_json(p/'PROOF.json',{'inputs_and_scripts_sha256':{},'outputs_sha256':{'data.txt':trainer.sha(f)}})
            trainer.verify_proof(p)
            f.write_text('changed')
            with self.assertRaises(ValueError):trainer.verify_proof(p)
if __name__=='__main__':unittest.main()

