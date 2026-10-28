"""Reference-cell loading and exact single-node temperature integration.

This implements the adopted calculation; it does not identify Z50 pack current
or a physically validated pack thermal model.
"""
from dataclasses import dataclass
import json, math
from pathlib import Path

@dataclass(frozen=True)
class ThermalModel:
    a: float
    b: float
    reference_capacity_ah: float = 2.5

    def __post_init__(self):
        if not all(math.isfinite(x) and x>0 for x in (self.a,self.b,self.reference_capacity_ah)):
            raise ValueError('Positive finite coefficients and reference capacity required')

    @classmethod
    def from_json(cls,path:Path):
        values=json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(values['a_K_per_A2_s'],values['b_per_s'],values['nominal_cell_capacity_Ah'])

    def equivalent_current(self,power_kw:float,nominal_energy_kwh:float)->float:
        if not math.isfinite(power_kw) or power_kw<0 or not math.isfinite(nominal_energy_kwh) or nominal_energy_kwh<=0:
            raise ValueError('Nonnegative demand and positive nominal energy required')
        return self.reference_capacity_ah*power_kw/nominal_energy_kwh

    def step(self,surface_c:float,air_c:float,current_a:float,duration_s:float,heating_multiplier:float=1.)->float:
        if not all(math.isfinite(x) for x in (surface_c,air_c,current_a,duration_s,heating_multiplier)) or duration_s<0 or heating_multiplier<=0:
            raise ValueError('Finite inputs, nonnegative duration and positive heating factor required')
        decay=math.exp(-self.b*duration_s)
        return air_c+(surface_c-air_c)*decay+heating_multiplier*self.a*current_a**2/self.b*(1.-decay)

    @property
    def time_constant_s(self)->float:return 1./self.b

    def equilibrium_rise_c(self,current_a:float,heating_multiplier:float=1.)->float:
        if not math.isfinite(current_a) or not math.isfinite(heating_multiplier) or heating_multiplier<=0:
            raise ValueError('Finite current and positive heating factor required')
        return heating_multiplier*self.a*current_a**2/self.b
