"""Independent accounting and electrical-anchor checks for the 27 October run."""
import unittest

import run_thermal as study


class ThermalAccountingTests(unittest.TestCase):
    def function(self, name):
        self.assertTrue(callable(getattr(study,name,None)), 'Missing calculation: '+name)
        return getattr(study,name)

    def test_energy_clips_both_ends_in_seconds_and_includes_stationary(self):
        fn=self.function('energy_between')
        events=[dict(start_s=0.,end_s=60.,energy_kwh=2.),
                dict(start_s=60.,end_s=180.,energy_kwh=6.)]
        self.assertAlmostEqual(fn(events,30.,120.),4.)

    def test_cycle_is_complete_unload_end_to_unload_end(self):
        fn=self.function('recurring_cycles')
        rows=[dict(SimulationTime=0.,ElapsedTime=2.,State='Loading',ElectricityFromBatteryConsumed=2.),
              dict(SimulationTime=2.,ElapsedTime=1.,State='Unloading',ElectricityFromBatteryConsumed=1.),
              dict(SimulationTime=3.,ElapsedTime=4.,State='TravelLoaded',ElectricityFromBatteryConsumed=8.),
              dict(SimulationTime=7.,ElapsedTime=1.,State='Unloading',ElectricityFromBatteryConsumed=1.),
              dict(SimulationTime=8.,ElapsedTime=.5,State='Unloading',ElectricityFromBatteryConsumed=.5)]
        cycles=fn(rows,8.5*60.)
        self.assertEqual(len(cycles),1)
        self.assertEqual(cycles[0]['start_s'],180.)
        self.assertEqual(cycles[0]['end_s'],480.)
        self.assertAlmostEqual(cycles[0]['energy_kwh'],9.)

    def test_cycle_cutoff_excludes_final_partial_cycle(self):
        fn=self.function('recurring_cycles')
        rows=[dict(SimulationTime=0.,ElapsedTime=1.,State='Unloading',ElectricityFromBatteryConsumed=1.),
              dict(SimulationTime=1.,ElapsedTime=2.,State='Loading',ElectricityFromBatteryConsumed=2.),
              dict(SimulationTime=3.,ElapsedTime=1.,State='Unloading',ElectricityFromBatteryConsumed=1.)]
        self.assertEqual(fn(rows,239.),[])
        self.assertEqual(len(fn(rows,240.)),1)

    def test_pulse_quotient_recovers_constant_resistor_both_signs(self):
        fn=self.function('pulse_edges')
        t=list(range(18))
        current=[0.]*6+[-20.]*6+[20.]*6
        voltage=[3.3+.01*i for i in current]
        edges=fn(t,current,voltage)
        self.assertEqual(len(edges),2)
        for edge in edges:
            self.assertAlmostEqual(edge['adjacent_apparent_r_ohm'],.01,places=12)
            self.assertAlmostEqual(edge['median3_apparent_r_ohm'],.01,places=12)

    def test_pulse_anchor_rejects_sparse_or_unstable_edge(self):
        fn=self.function('pulse_edges')
        t=[0.,60.,120.,180.,240.,300.]
        current=[0.,0.,0.,20.,20.,20.]
        voltage=[3.3+.01*i for i in current]
        self.assertEqual(fn(t,current,voltage),[])

    def test_laboratory_temperature_fields_preserve_record_aliases(self):
        fn=self.function('temperature_channels')
        self.assertEqual(fn({'SurfaceTemperature':[25.],'AirTemperature':[24.]}),([25.],[24.]))
        self.assertEqual(fn({'Ts1':[35.],'Tf':[34.]}),([35.],[34.]))
        self.assertEqual(fn({'Ts':[45.],'Tf':[44.]}),([45.],[44.]))


if __name__=='__main__':
    unittest.main(verbosity=2)
