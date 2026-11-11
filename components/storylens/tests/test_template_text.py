"""Regression contracts for the final native template-text pass. Owner runs suites."""
import unittest
from hinglish_app.template_text_model import validate_snapshot,build_slots,align_script,validated_choices,signature,speech_normal,group_choices,expand_choices,limit_visible_text,sparse_choices,keyed_request,keyed_choices,bridge_short_gaps,uncovered_headings


def snapshot():
    return {'version':1,'project_id':'owner.aep','composition_id':'42','duration':60,'fps':30,'fingerprint':'native-1','templates':[{'layer_id':'9','source_id':'10','start':0,'end':60,'texts':[{'id':'20:1','comp_id':'20','layer_index':1,'layer_id':'30','name':'Title','text':'LOREM IPSUM','font_size':60,'expression':'','enabled':True,'runs':[{'start':3,'end':8}],'bounds':{'width':600,'height':100}}]}],'audio':[{'path':'D:/source.mp4','start':0,'end':60,'source_in':0,'rate':1,'gain':1}], 'warnings':[]}

class TemplateTextModelTests(unittest.TestCase):
    def test_decorative_lettering_does_not_fill_a_heading_quota(self):
        slots=[{'id':'decor','policy':'choose','font_size':300,'background_text':True,
                'runs':[{'start':0,'end':10}]}]
        self.assertEqual(uncovered_headings(slots,[]),[])

    def test_off_camera_and_tiny_titles_cannot_occupy_a_scene_heading(self):
        slots=[{'id':'tiny','policy':'choose','font_size':300,'projected':{'usable':False},'runs':[{'start':0,'end':10}]},
               {'id':'title','policy':'choose','font_size':50,'projected':{'usable':True,'height':45},'runs':[{'start':0,'end':10}]}]
        self.assertEqual([s['id'] for s in uncovered_headings(slots,[])],['title'])

    def test_background_title_does_not_suppress_three_foreground_scenes(self):
        slots=[{'id':'background','policy':'choose','font_size':300,'display_opacity':.4,
                'runs':[{'start':0,'end':30}]}]
        slots += [{'id':str(i),'policy':'choose','font_size':60,'display_opacity':1,
                   'runs':[{'start':i*10,'end':i*10+10}]} for i in range(3)]
        self.assertEqual([s['id'] for s in uncovered_headings(slots,[])],['0','1','2'])
        actions=[{'id':s['id'],'action':'replace','role':'heading','text':'Mumbai','word_indices':[0]} for s in slots]
        self.assertEqual([a['id'] for a in limit_visible_text(slots,actions) if a['action']=='replace'],['0','1','2'])

    def test_short_scene_transitions_do_not_remove_the_next_heading(self):
        slots=[{'id':str(i),'policy':'choose','font_size':60,
                'runs':[{'start':i*5,'end':i*5+5.5}]} for i in range(3)]
        self.assertEqual(len(uncovered_headings(slots,[])),3)

    def test_full_length_lettering_does_not_win_over_scene_titles(self):
        slots=[{'id':'broad','policy':'choose','font_size':300,'runs':[{'start':0,'end':30}]}]
        slots += [{'id':str(i),'policy':'choose','font_size':60,
                   'runs':[{'start':i*10,'end':i*10+10}]} for i in range(3)]
        self.assertEqual([s['id'] for s in uncovered_headings(slots,[])],['0','1','2'])

    def test_heading_catalog_rejects_tiny_slot_but_allows_large_display_font_to_fit(self):
        from hinglish_app.template_text_model import heading_candidates
        words=[{'text':t,'script_index':i} for i,t in enumerate('Sachin Tendulkar'.split())]
        slot={'words':words,'font_size':316,'bounds':{'width':900}}
        self.assertIn('Sachin Tendulkar',[c['text'] for c in heading_candidates(slot)])
        slot.update(font_size=36,bounds={'width':80})
        self.assertNotIn('Sachin Tendulkar',[c['text'] for c in heading_candidates(slot)])

    def test_heading_catalog_keeps_grounded_names_and_rejects_filler_and_gaps(self):
        from hinglish_app.template_text_model import heading_candidates,catalog_choice
        words=[{'text':t,'script_index':i} for i,t in enumerate('Rohit Sharma aur Mumbai Indians'.split())]
        slot={'id':'s','template_layer_id':'9','text_id':'1','policy':'choose','max_words':4,'words':words}
        candidates=heading_candidates(slot)
        self.assertIn('Rohit Sharma',[c['text'] for c in candidates])
        self.assertEqual([c['text'] for c in heading_candidates(slot,{('rohit','sharma')})],['Rohit Sharma'])
        self.assertNotIn('aur',[c['text'] for c in candidates])
        self.assertNotIn('Sharma aur',[c['text'] for c in candidates])
        chosen=next(i for i,c in enumerate(candidates) if c['text']=='Mumbai Indians')
        self.assertEqual(catalog_choice(slot,candidates,chosen)['text'],'Mumbai Indians')
        self.assertEqual(catalog_choice(slot,candidates,-1)['action'],'hide')
        with self.assertRaises(ValueError):catalog_choice(slot,candidates,999)
        slot['words']=[words[0],{**words[1],'script_index':4}]
        self.assertNotIn('Rohit Sharma',[c['text'] for c in heading_candidates(slot)])
        slot['words']=[{'text':'achha','script_index':0}]
        self.assertEqual(heading_candidates(slot),[])

    def test_short_alignment_gap_restores_phrase_but_not_an_unheard_paragraph(self):
        words=[{'text':'Rohit','script_index':0,'start':1,'end':1.2}, {'text':'batting','script_index':2,'start':1.8,'end':2}]
        result=bridge_short_gaps('Rohit Sharma batting',words)
        self.assertEqual([w['text'] for w in result],['Rohit','Sharma','batting'])
        self.assertEqual(result[1]['alignment'],'bounded_interpolation')
        distant=[words[0],{**words[1],'start':15,'end':16}]
        self.assertEqual(len(bridge_short_gaps('Rohit Sharma batting',distant)),2)
        # Numbers must remain directly heard; never interpolate a score or year.
        self.assertEqual(len(bridge_short_gaps('Rohit 100 batting',words)),2)

    def test_heading_repair_targets_uncovered_scenes_not_every_echo_layer(self):
        slots=[{'id':str(i),'policy':'choose','existing_date':False,'font_size':100-i,
                'runs':[{'start':0 if i<2 else 10,'end':5 if i<2 else 15}]} for i in range(4)]
        self.assertEqual([s['id'] for s in uncovered_headings(slots,[])],['0','2'])
        self.assertEqual([s['id'] for s in uncovered_headings(slots,[{'id':'0','action':'replace','role':'heading'}])],['2'])

    def test_model_keys_are_short_and_each_schema_only_allows_its_local_words(self):
        s={'id':'very/long/native/path','template_layer_id':'9','text_id':'1','policy':'choose','words':[{'script_index':23,'text':'Mumbai'}],'max_words':4,'_planner_words':[{'script_index':23,'text':'Mumbai'}]}
        rows,schema=keyed_request([s]);self.assertEqual(rows[0]['id'],'0')
        self.assertEqual(schema['properties']['choices']['properties']['0']['properties']['text']['maxLength'],80)
        self.assertEqual(keyed_choices([s],{'choices':{'0':{'role':'heading','text':'Mumbai'}}})[0]['text'],'Mumbai')
        self.assertEqual(keyed_choices([s],{'choices':{'0':{'role':'heading','text':'Chennai'}}})[0]['action'],'hide')
        self.assertEqual(keyed_choices([s],{'choices':{}})[0]['action'],'hide')
    def test_sparse_plan_hides_unused_and_unsupported_slots_without_inventing_words(self):
        a={'id':'a','template_layer_id':'9','text_id':'1','policy':'choose','words':[{'script_index':0,'text':'Mumbai'}],'max_words':4}
        b={**a,'id':'b','text_id':'2'};c={**a,'id':'c','text_id':'3'}
        result=sparse_choices([a,b,c],{'choices':[{'id':'a','role':'heading','word_indices':[0]},{'id':'b','role':'heading','word_indices':[999]}]})
        self.assertEqual([r['action'] for r in result],['replace','hide','hide'])
        self.assertEqual(result[0]['text'],'Mumbai');self.assertEqual(result[1]['text'],'')
    def test_sparse_plan_rejects_unknown_layer_identity(self):
        with self.assertRaises(ValueError):sparse_choices([],{'choices':[{'id':'unknown','role':'heading','word_indices':[0]}]})
    def test_empty_text_is_switched_off_without_asking_the_model(self):
        a=snapshot();a['templates'][0]['texts'][0]['text']=' \r\n\t'
        self.assertEqual(build_slots(a,[{'text':'Mumbai','start':4,'end':5,'script_index':0}])[0]['policy'],'hide')
    def test_weak_headings_are_hidden_instead_of_stopping_all_templates(self):
        s={'id':'a','template_layer_id':'9','text_id':'1','policy':'choose','words':[{'script_index':0,'text':'hai'}],'max_words':4}
        answer={'choices':[{'id':'a','action':'replace','role':'heading','word_indices':[0]}]}
        self.assertEqual(validated_choices([s],answer)[0]['action'],'hide')
    def test_only_main_heading_and_short_subheading_remain_at_one_time(self):
        slots=[{'id':str(i),'font_size':100-i*10,'runs':[{'start':0 if i<4 else 10,'end':5 if i<4 else 15}]} for i in range(5)]
        actions=[{'id':str(i),'action':'replace','role':'heading' if i in (0,1,4) else 'support','text':'Mumbai wins','word_indices':[1,2]} for i in range(5)]
        kept=limit_visible_text(slots,actions)
        self.assertEqual([x['id'] for x in kept if x['action']=='replace'],['0','2','4'])
    def test_stock_labels_and_multi_year_rulers_are_hidden_without_model(self):
        for text in ['COPIES AND ACCESSORIES 000-68','put here your content','1920 1930 1940 1950','AFTEREFFESCT  PHOTO SLIDE','Photo Frame 09','After Effects cs6 & up','Lorem ipsum dolor sit amet, consectetur adipiscing elit,']:
            a=snapshot();a['templates'][0]['texts'][0]['text']=text
            self.assertEqual(build_slots(a,[{'text':'Mumbai','start':4,'end':5,'script_index':0}])[0]['policy'],'hide')
    def test_date_without_spoken_year_is_hidden_but_supported_year_goes_to_planner(self):
        a=snapshot();a['templates'][0]['texts'][0]['text']='1840'
        self.assertEqual(build_slots(a,[{'text':'Mumbai','start':4,'end':5,'script_index':0}])[0]['policy'],'hide')
        self.assertEqual(build_slots(a,[{'text':'2013','start':4,'end':5,'script_index':0}])[0]['policy'],'choose')
    def test_identical_visible_echoes_share_choice_but_other_times_do_not(self):
        a=build_slots(snapshot(),[{'text':'Mumbai','start':4,'end':5,'script_index':0}])[0]
        b={**a,'id':'duplicate','text_id':'duplicate'};c={**a,'id':'later','runs':[{'start':20,'end':25}]}
        representatives,groups=group_choices([a,b,c])
        self.assertEqual(len(representatives),2)
        choices=[{'id':a['id'],'text':'Mumbai','action':'replace','word_indices':[0],'role':'heading','template_layer_id':a['template_layer_id'],'text_id':a['text_id']}]
        expanded=expand_choices(choices,groups)
        self.assertEqual([r['id'] for r in expanded],[a['id'],'duplicate'])
        self.assertEqual(expanded[1]['text_id'],'duplicate')
    def test_romanized_long_vowels_and_aspirated_f_preserve_spoken_matches(self):
        self.assertEqual(speech_normal('mumbaaii'),speech_normal('Mumbai'))
        self.assertEqual(speech_normal('kaaphii'),speech_normal('kaafi'))
        self.assertEqual(speech_normal('thaa'),speech_normal('tha'))
        self.assertNotEqual(speech_normal('2008'),speech_normal('2009'))
    def test_long_hinglish_spelling_differences_keep_real_word_times(self):
        source=['Mumbaai','Indiyans','apne','peek','leval','par','thi']
        observed=[{'text':w,'start':i,'end':i+.4} for i,w in enumerate(source)]
        words=align_script('Mumbai Indians apne peak level par thi',observed)
        self.assertEqual([w['script_index'] for w in words],list(range(7)))
        self.assertEqual([w['start'] for w in words],list(range(7)))
    def test_similar_years_are_not_fuzzy_matched(self):
        words=align_script('Mumbai won 2008 then Chennai won 2009',[{'text':w,'start':i,'end':i+.5} for i,w in enumerate('Mumbai won 2009 then Chennai won 2008'.split())])
        self.assertNotIn(2,[w['script_index'] for w in words]);self.assertNotIn(6,[w['script_index'] for w in words])
    def test_stale_signature_changes_with_trim_and_audio(self):
        a=snapshot();before=signature(a);a['templates'][0]['end']=59;self.assertNotEqual(before,signature(a));a=snapshot();a['audio'][0]['source_in']=2;self.assertNotEqual(before,signature(a))
    def test_snapshot_rejects_unbounded_or_invalid_timing(self):
        a=snapshot();a['templates'][0]['texts'][0]['runs'][0]['end']=999
        with self.assertRaises(ValueError):validate_snapshot(a)
    def test_slots_use_text_intervals_not_whole_template(self):
        words=[{'text':'Mumbai','start':4,'end':4.4,'script_index':0},{'text':'wins','start':4.5,'end':5,'script_index':1},{'text':'unrelated','start':35,'end':36,'script_index':2}]
        slots=build_slots(snapshot(),words);self.assertEqual([w['script_index'] for w in slots[0]['words']],[0,1])
    def test_long_filler_is_hidden_without_model_authorship(self):
        a=snapshot();a['templates'][0]['texts'][0]['text']='Lorem ipsum '+('dummy paragraph '*30)
        self.assertEqual(build_slots(a,[])[0]['policy'],'hide')
    def test_expression_text_is_reported_not_overwritten(self):
        a=snapshot();a['templates'][0]['texts'][0]['expression']='comp("Controller").layer("Title").text.sourceText'
        self.assertEqual(build_slots(a,[])[0]['policy'],'skip')
    def test_expression_filler_can_be_hidden_without_rewriting_expression(self):
        a=snapshot();row=a['templates'][0]['texts'][0];row['text']='Lorem ipsum '+('dummy paragraph '*30);row['expression']='value';self.assertEqual(build_slots(a,[])[0]['policy'],'hide')
    def test_text_mattes_are_never_hidden_as_filler(self):
        a=snapshot();row=a['templates'][0]['texts'][0];row['text']='Lorem ipsum '+('dummy paragraph '*30);row['unsafe']='Text used as a track matte is kept.';self.assertEqual(build_slots(a,[])[0]['policy'],'skip')
    def test_script_alignment_does_not_invent_times_for_missing_paragraph(self):
        result=align_script('Mumbai won. This entire paragraph was removed. Chennai won.',[{'text':'Mumbai','start':0,'end':1},{'text':'won','start':1,'end':2},{'text':'Chennai','start':40,'end':41},{'text':'won','start':41,'end':42}])
        self.assertEqual([r['script_index'] for r in result],[0,1,7,8])
    def test_dates_must_come_from_local_spoken_words(self):
        slots=[{'id':'a','template_layer_id':'9','text_id':'1','policy':'choose','words':[{'script_index':1,'text':'Mumbai'}],'max_words':6}]
        with self.assertRaises(ValueError):validated_choices(slots,{'choices':[{'id':'a','action':'replace','role':'date','word_indices':[1900]}]})
    def test_missing_model_choices_are_not_silently_applied(self):
        with self.assertRaises(ValueError):validated_choices([{'id':'a','template_layer_id':'9','text_id':'1','policy':'choose','words':[],'max_words':6}],{'choices':[]})
    def test_model_can_only_select_real_local_words_in_reading_order(self):
        slots=[{'id':'a','template_layer_id':'9','text_id':'1','policy':'choose','words':[{'script_index':4,'text':'Mumbai'},{'script_index':5,'text':'wins'}],'max_words':6}]
        result=validated_choices(slots,{'choices':[{'id':'a','action':'replace','role':'heading','word_indices':[4,5]}]});self.assertEqual(result[0]['text'],'Mumbai wins')
        with self.assertRaises(ValueError):validated_choices(slots,{'choices':[{'id':'a','action':'replace','role':'heading','word_indices':[5,4]}]})
    def test_template_is_not_one_generic_title(self):
        a=snapshot();b={**a['templates'][0]['texts'][0],'id':'20:2','layer_index':2,'runs':[{'start':40,'end':45}]};a['templates'][0]['texts'].append(b)
        words=[{'text':'Mumbai','start':4,'end':5,'script_index':0},{'text':'Chennai','start':41,'end':42,'script_index':1}];slots=build_slots(a,words);self.assertEqual(len(slots),2);self.assertNotEqual(slots[0]['words'],slots[1]['words'])
    def test_both_no_audio_and_empty_script_fail_before_job(self):
        a=snapshot();a['audio']=[]
        with self.assertRaises(ValueError):validate_snapshot(a)

if __name__=='__main__':unittest.main()

