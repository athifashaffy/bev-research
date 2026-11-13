"""Test the actual example-construction boundary, including target separation."""
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
if (BASE/'train.py').exists():
    spec=importlib.util.spec_from_file_location('causal_training',BASE/'train.py')
    trainer=importlib.util.module_from_spec(spec);spec.loader.exec_module(trainer)
else:trainer=None

class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(trainer,'Corrected trainer is missing')
        self.case={'grid_s':np.arange(301),'grid_values':np.tile([25.,9.,25.],(301,1)),
                   'capacity_kwh':2.5,'rr_pct':3.}
        self.events=[dict(start_s=0.,end_s=100.,energy_kwh=100/3600),
                     dict(start_s=100.,end_s=400.,energy_kwh=1.)]

    def test_target_changes_do_not_change_causal_features(self):
        first=trainer.make_examples('test',self.case,self.events,60,'completed_events')
        self.case['grid_values'][:,0]=50.
        self.case['grid_values'][:,1]=99.
        second=trainer.make_examples('test',self.case,self.events,60,'completed_events')
        np.testing.assert_array_equal(first['x'],second['x'])
        np.testing.assert_array_equal(first['target_c'],np.full(19,25.))
        np.testing.assert_array_equal(second['target_c'],np.full(19,50.))
        self.assertTrue(np.all(first['source_end_s']<=first['origin_s']))

    def test_completed_event_is_not_current_unfinished_event(self):
        result=trainer.make_examples('test',self.case,self.events,60,'completed_events')
        index=result['origin_s'].tolist().index(150)
        self.assertEqual(result['current_a'][index],1.)
        self.assertEqual(result['source_end_s'][index],100.)
        self.assertEqual(result['origin_s'].tolist(),list(range(60,241,10)))

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            trainer.make_examples('test',self.case,self.events,60,'typo')

    def test_control_protocol_discloses_unfinished_event_inputs(self):
        make_protocol=getattr(trainer,'make_protocol',None)
        self.assertIsNotNone(make_protocol,'Mode-specific protocol builder is missing')
        control=make_protocol('retrospective_control')
        causal=make_protocol('completed_events')
        self.assertTrue(control['allows_unfinished_event_inputs'])
        self.assertFalse(causal['allows_unfinished_event_inputs'])
        self.assertEqual(control['temperature_input_kind'],'retrospective_target_history')
        self.assertEqual(causal['temperature_input_kind'],'estimated_from_completed_events')

if __name__=='__main__':unittest.main()
