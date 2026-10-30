"""Validated anonymous worker intervals on the reference B clock."""

import math
import re


def validate_worker_spans(document, coverages=None):
    if document.get('version')!=1 or not isinstance(document.get('spans'),list) or not document['spans']:
        raise ValueError('Invalid worker span document')
    seen=set();groups={}
    for row in document['spans']:
        if (set(row)!={'session','span_id','start_wall','end_wall','worker_id'}
                or not isinstance(row['session'],str) or not isinstance(row['span_id'],str)
                or not re.fullmatch(r'\d{8}',row['session'])
                or not re.fullmatch(r'[A-Za-z0-9_-]+',row['span_id']) or row['span_id'] in seen
                or row['worker_id'] not in ('P1','P2','P3','P4')
                or not all(type(row[k]) in (int,float) and math.isfinite(row[k]) for k in ('start_wall','end_wall'))
                or row['start_wall']>=row['end_wall']):
            raise ValueError('Invalid anonymous worker interval')
        seen.add(row['span_id']);groups.setdefault(row['session'],[]).append(row)
        if coverages is not None:
            bounds=coverages.get(row['session'])
            if bounds is None or row['start_wall']<bounds[0] or row['end_wall']>bounds[1]:
                raise ValueError('Worker interval outside overlap bounds')
    for rows in groups.values():
        ordered=sorted(rows,key=lambda r:r['start_wall'])
        if any(a['end_wall']>b['start_wall'] for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Worker intervals overlap')
    for gap in document.get('handover_intervals',[]):
        if (not all(type(gap[k]) in (int,float) and math.isfinite(gap[k]) for k in ('start_wall','end_wall'))
                or gap['start_wall']>=gap['end_wall']):
            raise ValueError('Invalid handover interval')
        if any(r['start_wall']<gap['end_wall'] and gap['start_wall']<r['end_wall']
               for r in groups.get(gap['session'],[])):
            raise ValueError('Handover interval belongs to a worker')
    return document


def assign_span(rows, session, start, end):
    candidates=[r for r in rows if r['session']==session]
    if not candidates: raise ValueError('No worker spans for '+session)
    def rank(row):
        overlap=max(0.,min(end,row['end_wall'])-max(start,row['start_wall']))
        distance=max(0.,row['start_wall']-end,start-row['end_wall'])
        return (-overlap,distance,row['start_wall'],row['span_id'])
    return min(candidates,key=rank)['span_id']
