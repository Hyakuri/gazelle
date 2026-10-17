"""Compare v2/v3 lag for the same source base time over the session span."""

from .sync_calibrate import corrected_time


def maximum_lag_difference(old,new,start,end):
    if start>=end:raise ValueError('A positive comparison span is required')
    boundaries={start,end}
    for fit in (old,new):
        if not fit:continue
        for left,right in zip(fit['segments'],fit['segments'][1:]):
            relative=right['start']
            if fit.get('time_domain')=='base':
                boundaries.add(fit['origin']+relative)
            else:
                # v2 defines b = t + L(t). Include both one-sided base limits.
                for segment in (left,right):
                    boundaries.add(fit['origin']+relative+segment['c0']+segment['c1']*relative)
    points=sorted({max(start,min(end,b+epsilon)) for b in boundaries for epsilon in (-1e-6,0.,1e-6)})
    rows=[]
    for b in points:
        before=corrected_time(b,old) if old else b
        after=corrected_time(b,new) if new else b
        rows.append(dict(base_time=b,old_lag_seconds=b-before,new_lag_seconds=b-after,
                         absolute_difference_seconds=abs(before-after)))
    maximum=max(r['absolute_difference_seconds'] for r in rows)
    return dict(maximum_seconds=maximum,retain_proxy=maximum<=.05,base_span=[start,end],
                method='piecewise-linear endpoints and one-sided cuts at the same source base time',samples=rows)
