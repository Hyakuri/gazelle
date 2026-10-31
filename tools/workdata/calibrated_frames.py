"""Stream base-time frames through explicit v3 cuts without reordering time."""

from .sync_calibrate import corrected_time


def segment_time(base, segment, origin):
    return base-segment['c0']-segment['c1']*(base-origin)


def uncertain_ranges(fit):
    ranges=[]
    for point,left,right in zip(fit['breakpoints'],fit['segments'],fit['segments'][1:]):
        values=[segment_time(fit['origin']+b,s,fit['origin'])
                for b in point['uncertainty_seconds'] for s in (left,right)]
        ranges.append([min(values),max(values)])
    return ranges


def is_uncertain(time,ranges):
    return any(start<=time<=end for start,end in ranges)


def calibrated_frames(frames,fit,ranges,stats):
    """Buffer only an impending overlap, then use the actual first post-cut T."""
    stats.update(excluded_overlap_frames=0,excluded_duplicate_times=0,peak_buffer_frames=0,transitions=[])
    cuts=fit['breakpoints'];segments=fit['segments'];origin=fit['origin']
    cut_index=0;pending=[];previous=None;last=-float('inf')
    def emit(row):
        nonlocal last
        value=row['wall_time']
        if value==last:
            stats['excluded_duplicate_times']+=1
            return None
        if value<last:
            raise ValueError('Selectable v3 frame times are not increasing')
        last=value
        return row
    try:
        for row in frames:
            base=row['wall_time'];value=corrected_time(base,fit)
            current=dict(row,base_time=base,wall_time=value)
            while cut_index<len(cuts) and base-origin>=cuts[cut_index]['seconds']:
                for buffered in pending:
                    if buffered['wall_time']>=value:
                        stats['excluded_overlap_frames']+=1
                    else:
                        selected=emit(buffered)
                        if selected is not None:yield selected
                pending=[]
                if previous is not None:
                    interval=sorted([previous,value]);ranges.append(interval)
                    stats['transitions'].append(dict(cut=cuts[cut_index]['seconds'],
                        previous_time=previous,first_postcut_time=value,range=interval))
                cut_index+=1
            previous=value
            threshold=None
            if cut_index<len(cuts):
                at=origin+cuts[cut_index]['seconds']
                before=segment_time(at,segments[cut_index],origin)
                after=segment_time(at,segments[cut_index+1],origin)
                if after<before:threshold=after
            if threshold is not None and value>=threshold:
                pending.append(current)
                stats['peak_buffer_frames']=max(stats['peak_buffer_frames'],len(pending))
            else:
                selected=emit(current)
                if selected is not None:yield selected
        for row in pending:
            selected=emit(row)
            if selected is not None:yield selected
    finally:
        if hasattr(frames,'close'):frames.close()
