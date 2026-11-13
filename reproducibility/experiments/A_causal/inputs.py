"""AI-assisted completed-event estimates and stable features, 12 Nov 2026.

The original event-average temperature is an offline target. These functions
construct estimates using only event reports available by the forecast origin.
"""
import bisect
import math
import numpy as np

A = 4.344635339312832e-05
B = .002655462788692412
DECIMALS = 12


def validate_events(events):
    previous = 0.
    for event in events:
        start, end, energy = (float(event[k]) for k in ('start_s','end_s','energy_kwh'))
        if not all(math.isfinite(v) for v in (start,end,energy)) or energy < 0 or end <= start:
            raise ValueError('Invalid event clock or energy')
        if abs(start-previous) > 1e-6:
            raise ValueError('Event ledger must be contiguous and nonoverlapping')
        previous = end


def advance(temperature, current, elapsed, air, a, b):
    heat = a*current*current
    if b == 0:
        return temperature + heat*elapsed
    return temperature + (air-temperature+heat/b)*(-math.expm1(-b*elapsed))


def history_as_of(events, origin_s, capacity_kwh, a=A, b=B, air_c=25., initial_c=25.):
    """Reconstruct t-60..t using only events ending by t, then hold known current.

    Reconstructed earlier samples may be revised when an event report arrives.
    Such revisions use information available at *this* origin. They never use
    the unfinished event's aggregate or observed temperature from its interior.
    """
    if not all(math.isfinite(v) for v in (origin_s,capacity_kwh,a,b,air_c,initial_c)):
        raise ValueError('Nonfinite model input')
    if origin_s < 60 or capacity_kwh <= 0 or a < 0 or b < 0:
        raise ValueError('Invalid history, capacity or thermal coefficients')
    validate_events(events)
    completed = [e for e in events if e['end_s'] <= origin_s]
    starts, currents, temperatures = [], [], []
    temperature = initial_c
    for event in completed:
        duration = event['end_s']-event['start_s']
        current = 2.5*(event['energy_kwh']*3600/duration)/capacity_kwh
        starts.append(event['start_s']);currents.append(current);temperatures.append(temperature)
        temperature = advance(temperature,current,duration,air_c,a,b)
    last_end = completed[-1]['end_s'] if completed else 0.
    last_current = currents[-1] if currents else 0.
    history=[]
    for t in origin_s + np.arange(-60.,1.):
        if t >= last_end:
            current=last_current
            temp=advance(temperature,current,t-last_end,air_c,a,b)
        else:
            index=bisect.bisect_right(starts,t)-1
            current=currents[index]
            temp=advance(temperatures[index],current,t-starts[index],air_c,a,b)
        history.append((temp,current,air_c))
    return np.array(history), {'completed_events':len(completed),
        'latest_available_event_end_s':last_end,'seconds_since_last_report':origin_s-last_end}


def stable_features(history, capacity_kwh, rr_pct):
    """Canonicalize insignificant digits and avoid backend-dependent dot sums."""
    values=np.asarray(history,dtype=float)
    if values.shape != (61,3) or not np.isfinite(values).all():
        raise ValueError('Expected 61 finite three-channel history samples')
    if not math.isfinite(capacity_kwh) or capacity_kwh<=0 or not math.isfinite(rr_pct):
        raise ValueError('Invalid configuration')
    row=[]
    for j in range(3):
        col=[round(float(x),DECIMALS) for x in values[:,j]]
        # Subtraction makes constant channels identically zero before summation.
        slope=math.fsum((i-30)*(v-col[-1]) for i,v in enumerate(col))/18910.
        row.extend([col[-1],math.fsum(col)/61,min(col),max(col),slope,col[-1]-col[-2]])
    row.extend([capacity_kwh,rr_pct])
    return np.array([round(float(v),DECIMALS)+0. for v in row])
