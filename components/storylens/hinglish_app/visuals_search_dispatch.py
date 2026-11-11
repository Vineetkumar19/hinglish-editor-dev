"""Explicitly distinguish unreviewed web options from the legacy verified edit."""

def method(payload):
    value=payload.get('visuals_search_method','website')
    if value not in ('website','verified'):
        raise ValueError('Choose website options or verified Smart Visuals.')
    return value


def arguments(payload):
    selected=method(payload)
    result=['--search-method',selected]
    if selected=='website':
        return result+['--evaluator','off']
    if payload.get('visuals_web') is False:result.append('--no-web')
    if payload.get('visuals_check') is False:result+=['--evaluator','off']
    return result


def summary(projects):
    rows=[(p,s) for p in projects for s in p.get('slots',[])]
    def budget(project):
        value=project.get('options_per_moment',5)
        return value if type(value) is int and value in (2,5) else 5
    manual=bool(projects) and all(p.get('search_method')=='website' for p in projects)
    collecting=any(p.get('collecting') for p in projects)
    return {'review_options':any(p.get('review_options') for p in projects),
        'subjects':len(rows),'options':sum(len(s.get('options',[])) for _,s in rows),
        'complete_subjects':sum(len(s.get('options',[]))>=budget(p) for p,s in rows),
        'selected':sum(bool(s.get('clip')) for _,s in rows),
        'research_complete':bool(projects) and not collecting,
        'partial':not projects or collecting or any(len(s.get('options',[]))<budget(p) for p,s in rows),
        **({'review_policy':'human','vision_checked':False} if manual else {})}
