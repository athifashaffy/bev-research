"""AI-assisted checks for simulator assumptions and forecast information boundaries."""
from pathlib import Path
import sys, unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import telemetry as live

def event(start,end,energy):
    return dict(start_s=start,end_s=end,energy_kwh=energy)

class LiveTests(unittest.TestCase):
    def test_fractional_boundaries_integrate_before_sampling(self):
        s=live.generate([event(0,1.5,1.5/3600),event(1.5,4,0)],2.5,4,a=1,b=0)
        np.testing.assert_allclose(s[:,0],[0,1,2,3,4])
        np.testing.assert_allclose(s[:,3],[25,26,26.5,26.5,26.5])
        np.testing.assert_allclose(s[:,2],[1,1,0,0,0])

    def test_current_switches_at_exact_boundary(self):
        s=live.generate([event(0,2,2/3600),event(2,4,0)],2.5,4,a=1,b=0)
        self.assertEqual(s[2,2],0);self.assertEqual(s[2,3],27)

    def test_future_activity_cannot_change_stream_prefix(self):
        first=event(0,90,90/3600)
        a=live.generate([first,event(90,120,0)],2.5,120)
        b=live.generate([first,event(90,120,1)],2.5,120)
        np.testing.assert_array_equal(a[:90],b[:90])

    def test_reserve_uses_all_energy(self):
        self.assertAlmostEqual(live.reserve_cutoff([event(0,3600,1)],1),2160)
        self.assertEqual(live.reserve_cutoff([event(0,3600,.1)],1),3600)

    def test_invalid_ledger_rejected(self):
        for events in ([event(0,0,1)],[event(1,2,1)],[event(0,2,-1)],
                       [event(0,2,1),event(3,4,1)]):
            with self.subTest(events=events),self.assertRaises(ValueError):
                live.generate(events,2.5,1)
        with self.assertRaises(ValueError):live.generate([event(0,2,1)],0,1)
        with self.assertRaises(ValueError):live.generate([event(0,2,1)],2.5,3)

    def stream(self,n=2001):
        t=np.arange(n,dtype=float)
        return np.column_stack((t,np.ones(n),np.ones(n),25+t*.001,np.full(n,25)))

    def test_prefix_features_never_read_future_rows(self):
        a=self.stream();b=a.copy();b[61:,2:]=999
        x=live.history_features(a[:61],354,3)
        np.testing.assert_array_equal(x,live.history_features(b[:61],354,3))
        self.assertEqual(x.shape,(20,));self.assertEqual(x[0],25.06)
        self.assertEqual(x[4],.001);self.assertEqual(x[16],0)

    def test_short_or_irregular_history_rejected(self):
        with self.assertRaises(ValueError):live.history_features(self.stream(60),354,3)
        a=self.stream(61);a[10,0]+=.1
        with self.assertRaises(ValueError):live.history_features(a,354,3)

    def test_target_is_future_and_30_minute_cutoff_is_exact(self):
        e=live.build_examples(self.stream(),354,3,1800)
        np.testing.assert_array_equal(e['origin_s'],np.arange(60,201,10))
        self.assertAlmostEqual(e['target_c'][0],26.86)
        self.assertAlmostEqual(e['delta_c'][0],1.8)
        self.assertEqual(e['x'][0,0],25.06)

    def test_mutating_future_changes_target_not_origin_features(self):
        a=self.stream();b=a.copy();b[61:,3]+=1
        ea=live.build_examples(a,354,3,60)
        eb=live.build_examples(b,354,3,60)
        np.testing.assert_array_equal(ea['x'][0],eb['x'][0])
        self.assertAlmostEqual(eb['target_c'][0]-ea['target_c'][0],1)

    def test_baselines_use_latest_state_and_past_slope(self):
        p=live.predict_history(self.stream(61),354,3,{60:None})
        self.assertEqual(p[60]['persistence'],25.06)
        self.assertAlmostEqual(p[60]['linear_trend'],25.12)
        self.assertLess(p[60]['physics_hold'],25.06)

if __name__=='__main__':unittest.main()

