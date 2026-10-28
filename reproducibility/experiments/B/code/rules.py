"""Experiment B rules: past-only 1 Hz sampling, full 60 s OLS and 5 s debounce."""
import bisect
import math
import statistics


def _values(time_s,values):
    t=[float(x) for x in time_s]
    y=[float(x) if x is not None else math.nan for x in values]
    if len(t)!=len(y) or not t:raise ValueError('Equal nonempty arrays are required')
    if any(not math.isfinite(x) for x in t) or any(b<=a for a,b in zip(t,t[1:])):
        raise ValueError('Finite strictly increasing timestamps are required')
    return t,y


def causal_grid(time_s,values,gap_limit=2.,max_age=1.01):
    """Latest native measurement at each integer second, never future interpolation.

    Segment IDs record every intervening missing raw sample, even when it occurs
    between grid instants. A raw sample may not be reused on a later grid point.
    """
    t,y=_values(time_s,values)
    segment=[];current=0
    for i,v in enumerate(y):
        if i and (t[i]-t[i-1]>gap_limit or not math.isfinite(v) or not math.isfinite(y[i-1])):current+=1
        segment.append(current)
    out={'time_s':[],'values':[],'measurement_time_s':[],'measurement_age_s':[],'segment':[]}
    previous_idx=None
    for second in range(math.ceil(t[0]),math.floor(t[-1])+1):
        index=bisect.bisect_right(t,second)-1
        age=second-t[index]
        value=y[index] if age<=max_age and index!=previous_idx else math.nan
        out['time_s'].append(float(second));out['values'].append(value)
        out['measurement_time_s'].append(t[index]);out['measurement_age_s'].append(age)
        out['segment'].append(segment[index]);previous_idx=index
    return out


def trailing_rate(values,segments):
    """61 consecutive one-second samples, including now, spanning past 60 s.

    Returns degrees Celsius per minute, None until the entire history is valid.
    """
    rates=[]
    for i in range(len(values)):
        rate=None
        if i>=60 and segments[i]==segments[i-60]:
            window=values[i-60:i+1]
            if all(v is not None and math.isfinite(v) for v in window):
                rate=60*math.fsum((j-30)*v for j,v in enumerate(window))/18910.
        rates.append(rate)
    return rates


def alarm_response(time_s,values,segments,threshold,rate=False):
    """Strict exceedance, first point crossing and first 5 elapsed-second alarm."""
    start=first=alarm=None
    eligible=predicate_count=0
    previous_t=previous_segment=None
    for t,v,segment in zip(time_s,values,segments):
        valid=v is not None and math.isfinite(v)
        eligible+=int(valid)
        exceeds=valid and v>threshold+(1e-10 if rate else 0.)
        predicate_count+=int(exceeds)
        if previous_t is not None and (t-previous_t>1.000001 or segment!=previous_segment):start=None
        if exceeds:
            if first is None:first=float(t)
            if start is None:start=t
            if alarm is None and t-start>=5.:alarm=float(t)
        else:start=None
        previous_t=t;previous_segment=segment
    return {'first_crossing_s':first,'alarm_s':alarm,'eligible_samples':eligible,
            'exceedance_samples':predicate_count,'debounce_s':5.}


def voltage_condition(time_s,voltage):
    """Prespecified <=0.1 V electrical condition with normal preheater context.

    This observable is not independently adjudicated physical TR/vent onset.
    Its native sampling bracket does not bound unknown clock alignment error.
    """
    t,u=_values(time_s,voltage)
    baseline=[v for ti,v in zip(t,u) if ti<0 and math.isfinite(v)]
    baseline_median=statistics.median(baseline) if baseline else None
    context=len(baseline)>=10 and 2.5<=baseline_median<=3.8
    result={'condition_start_s':None,'confirmed_s':None,'bracket_s':None,
            'baseline_preheater_median_v':baseline_median,'baseline_preheater_samples':len(baseline),
            'normal_voltage_context':context,'definition':'Native voltage <=0.1 V for 5 elapsed s, with normal preheater context'}
    if not context:return result
    start=bracket=None
    for i,(ti,vi) in enumerate(zip(t,u)):
        if i and t[i]-t[i-1]>2.:start=bracket=None
        if ti>=0 and math.isfinite(vi) and vi<=.1:
            if start is None:
                if i and math.isfinite(u[i-1]) and u[i-1]>.1 and ti-t[i-1]<=2.:
                    start=ti;bracket=[t[i-1],ti]
            if start is not None and ti-start>=5.:
                result.update(condition_start_s=start,confirmed_s=ti,bracket_s=bracket)
                break
        else:start=bracket=None
    return result
