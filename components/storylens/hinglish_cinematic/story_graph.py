"""Cricket documentary promises and protected source/timeline spans."""
import math
from .curation import digest


def validate_graph(graph,sources,body_duration):
    if graph.get('category')!='cricket':raise ValueError('Documentary introductions are cricket-only.')
    if not graph.get('script_hash') or not graph.get('transcript_hash') or not graph.get('body_hash'):
        raise ValueError('Bind the graph to the script, transcript and body timeline.')
    nodes=graph.get('nodes',[])
    if not nodes or len(nodes)>10000:raise ValueError('Supply a bounded source-backed story graph.')
    by_id={}
    for node in nodes:
        id=node.get('id')
        if not isinstance(id,str) or not id or id in by_id:raise ValueError('Story nodes need unique identities.')
        if node.get('kind') not in ('setup','question','evidence','payoff','title','bridge'):raise ValueError('Choose a supported story-node role.')
        if not isinstance(node.get('text'),str) or not node['text'].strip():raise ValueError('Every story node needs its actual source wording.')
        source=sources.get(node.get('source_id'))
        if source is None:raise ValueError('A story node refers to an unknown source.')
        times=[node.get(k) for k in ('source_start','source_end','body_start','body_end')]
        if any(not isinstance(t,(int,float)) or not math.isfinite(t) for t in times):raise ValueError('Use finite source and body times.')
        a,b,c,d=times
        if not 0<=a<b<=source['duration'] or not 0<=c<d<=body_duration:raise ValueError('Story-node times exceed their source or body.')
        if node.get('word_boundary_review') is not True:raise ValueError('Check complete speech/negation boundaries for each story node.')
        by_id[id]=node
    links=graph.get('question_payoffs',[])
    questions={n['id'] for n in nodes if n['kind']=='question'}
    linked=set()
    for link in links:
        question=by_id.get(link.get('question_id'));payoff=by_id.get(link.get('payoff_id'))
        if not question or question['kind']!='question' or not payoff or payoff['kind']!='payoff':raise ValueError('Map each question to a real payoff node.')
        if not link.get('evidence_ids') or any(e not in by_id or by_id[e]['kind']!='evidence' for e in link['evidence_ids']):raise ValueError('Record the evidence that answers the question.')
        linked.add(question['id'])
    if questions-linked:raise ValueError('Some promised questions have no answer in the body.')
    visual_ranges=graph.get('protected_visuals',[])
    if not isinstance(visual_ranges,list) or len(visual_ranges)>1000:
        raise ValueError('Enter a bounded list of protected picture ranges.')
    for entry in visual_ranges:
        if not isinstance(entry,dict):
            raise ValueError('Enter a picture range with its source and time.')
        source=sources.get(entry.get('source_id'))
        start,end=entry.get('start'),entry.get('end')
        reason=entry.get('reason')
        if (source is None or not all(type(t) in (int,float) and math.isfinite(t) for t in (start,end))
                or not 0<=start<end<=source['duration'] or not isinstance(reason,str) or not reason.strip()
                or len(reason)>240):
            raise ValueError('Protect each revealing picture with its actual source range and a short reason.')
    protected=[n for n in nodes if n['kind']=='payoff' or n.get('reveals_payoff')]
    if not protected:raise ValueError('Mark the payoff and revealing visuals before creating the trailer.')
    if graph.get('spoiler_review')!='approved':raise ValueError('Review scoreboards, captions, quotations and revealing visuals.')
    return {**graph,'protected_node_ids':[n['id'] for n in protected],'graph_hash':digest(graph),'review_state':'approved'}


def protect_sources(sources,graph):
    result={id:{**source,'protected_spans':list(source.get('protected_spans',[]))} for id,source in sources.items()}
    for node in graph['nodes']:
        if node['id'] in graph['protected_node_ids'] and node['source_id'] in result:
            result[node['source_id']]['protected_spans'].append({'start':node['source_start'],'end':node['source_end'],'node_id':node['id']})
    for entry in graph.get('protected_visuals',[]):
        if entry['source_id'] in result:
            result[entry['source_id']]['protected_spans'].append({'start':entry['start'],'end':entry['end'],
                'reason':entry['reason'],'kind':'visual'})
    return result


def validate_promises(plan,graph):
    by_id={n['id']:n for n in graph['nodes']}
    links={(l['question_id'],l['payoff_id']):l for l in graph['question_payoffs']}
    promised=set()
    for promise in plan.get('promises',[]):
        key=(promise.get('question_id'),promise.get('payoff_id'))
        if key not in links:raise ValueError('This trailer promises an unverified question or answer.')
        promised.add(key[0])
        payoff=by_id[key[1]]
        if promise['payoff_timestamp']!=payoff['body_start'] or promise.get('evidence_id') not in links[key]['evidence_ids']:
            raise ValueError('The promise does not match the reviewed body evidence.')
    for span in plan['source_spans']:
        node=by_id.get(span.get('node_id'))
        if not node or node['kind'] not in ('setup','question','title','bridge') or node['id'] in graph['protected_node_ids']:
            raise ValueError('Choose reviewed setup/question/bridge material for the intro.')
        if node['source_id']!=span['source_id'] or span['start']!=node['source_start'] or span['end']!=node['source_end']:
            raise ValueError('Keep the reviewed complete speech span intact; do not cut words or negations.')
        if node['kind']=='question' and node['id'] not in promised:raise ValueError('Every included question needs its explicit payoff promise.')
        if abs(span['frames']/float(plan['fps'])-(span['end']-span['start']))>1/float(plan['fps']):raise ValueError('Do not shorten reviewed speech to fit the intro; choose complete spans.')
    return True
