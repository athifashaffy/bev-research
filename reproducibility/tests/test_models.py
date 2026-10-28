from pathlib import Path
import math,unittest
from bev_research.thermal_model import ThermalModel
from bev_research.haulage import reserve_score,validate_events,complete_cycles

class ThermalTests(unittest.TestCase):
    def setUp(self):self.m=ThermalModel(4.344635339312832e-5,.002655462788692412)
    def test_mapping_and_time_constant(self):
        self.assertAlmostEqual(self.m.equivalent_current(141.6,354),1.)
        self.assertAlmostEqual(self.m.time_constant_s,376.5821928509924)
    def test_zero_current_cooling(self):
        self.assertAlmostEqual(self.m.step(35,25,0,100),25+10*math.exp(-self.m.b*100))
    def test_step_composition(self):
        once=self.m.step(25,25,2,60)
        twice=self.m.step(self.m.step(25,25,2,30),25,2,30)
        self.assertAlmostEqual(once,twice,places=12)
    def test_equilibrium_invariant(self):
        equilibrium=25+self.m.equilibrium_rise_c(2)
        self.assertAlmostEqual(self.m.step(equilibrium,25,2,300),equilibrium,places=12)
    def test_reject_invalid_parameters(self):
        with self.assertRaises(ValueError):ThermalModel(1,0)
        with self.assertRaises(ValueError):self.m.equivalent_current(1,0)
        with self.assertRaises(ValueError):self.m.step(25,25,1,-1)

class ReserveTests(unittest.TestCase):
    def event(self,start,duration,energy,state='TravelLoaded',quantity=0):
        return dict(SimulationTime=start,ElapsedTime=duration,ElectricityFromBatteryConsumed=energy,State=state,Quantity=quantity,DistanceTravelled=1)
    def test_cutoff_clips_mean_power_and_credit_requires_completion(self):
        rows=[self.event(0,10,50),self.event(10,1,5,'Unloading',45),self.event(11,10,50)]
        score=reserve_score(rows,100)
        self.assertAlmostEqual(score['cutoff_min'],12)
        self.assertEqual(score['completed_loads'],1)
        self.assertEqual(score['completed_tonnes'],45)
    def test_delivery_at_cutoff_counts(self):
        rows=[self.event(0,10,55),self.event(10,1,5,'Unloading',45)]
        self.assertEqual(reserve_score(rows,100)['completed_loads'],1)
    def test_gap_is_not_silently_filled(self):
        with self.assertRaises(ValueError):validate_events([self.event(0,1,1),self.event(2,1,1)])

if __name__=='__main__':unittest.main()
