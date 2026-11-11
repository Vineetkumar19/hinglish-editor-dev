"""Let the local judge verify adjacent requirements covered by one passage."""
from .core import fact_concerns


def verify_shared_passages(rows, judge, settings):
    result=[]
    for index,row in enumerate(rows):
        previous=result[-1] if result else None
        if previous and previous['paragraph_index']==row['paragraph_index']:
            left,right=previous.get('selected'),row.get('selected')
            # The sequence solver correctly prohibits replaying the same words.
            # A single recorded sentence may cover two adjacent script clauses.
            if bool(left)!=bool(right):
                selected=left or right
                other=row if left else previous
                inner=selected['span']
                # A verified clause may use only the end of a longer candidate
                # that covers both requirements. Exact-ID matching missed those
                # cases and left the first clause unmatched after sequence solving.
                candidates=[c for c in other.get('alternatives',[]) if c.get('eligible')
                    and c['span'].media_id==inner.media_id
                    and c['span'].first<=inner.first and c['span'].last>=inner.last
                    and c['span'].start<=inner.start and c['span'].end>=inner.end]
                candidates.sort(key=lambda c:(c['span'].id!=inner.id,c['span'].end-c['span'].start))
                occupied=[r['selected']['span'] for r in result[:-1]+rows[index+1:]
                          if r.get('selected')]
                merged=False
                for candidate in candidates:
                    outer=candidate['span']
                    tolerance=1/candidate.get('source_frame_rate',30)
                    if any(s.media_id==outer.media_id and (
                            max(s.first,outer.first)<min(s.last,outer.last) or
                            min(s.end,outer.end)-max(s.start,outer.start)>tolerance+1e-9)
                           for s in occupied):
                        continue
                    idea=previous['idea']+' '+row['idea']
                    spoken=outer.text
                    verdict=judge.compare(idea,[spoken])[0]
                    if (verdict['status']=='complete' and not verdict['repeated']
                            and not fact_concerns(idea,spoken,settings.protected_terms)):
                        chosen={**candidate,'verdict':verdict}
                        issues=list(dict.fromkeys(i for r in (previous,row) for i in r['issues']
                                                  if i!='sentence_not_matched'))
                        result[-1]={**previous,'idea':idea,'selected':chosen,'alternatives':[chosen],
                            'issues':issues,'selection_status':'meaning_model_selected',
                            'joined_requirements':previous.get('joined_requirements',[previous['idea']])+[row['idea']]}
                        merged=True
                        break
                if merged:continue
        result.append(row)
    return [{**row,'index':i} for i,row in enumerate(result)]
