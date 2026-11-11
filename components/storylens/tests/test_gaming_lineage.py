"""Synthetic timing/provenance fixtures; never local-model or render acceptance."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hinglish_niche.gaming_lineage import (
    build_highlights, compose_short, source_record, file_identity,
    write_new_record, load_highlights, capture_short, capture_highlights, LineageError,
    observe_video,
)


ROOT_SHA, OUTPUT_SHA, SHORT_SHA = 'a' * 64, 'b' * 64, 'c' * 64


def evidence(count, *, offset=0, step=1, prefix='frame', fps=(30, 1)):
    return dict(codec='h264', fps=list(fps), timebase=[1, 30],
                pts=[offset + i * step for i in range(count)],
                packets=[hashlib.sha256((prefix + str(i)).encode()).hexdigest() for i in range(count)])


def root():
    return source_record(ROOT_SHA, evidence(600))


def part(first, frames, prefix, kind='root'):
    return dict(kind=kind, source_sha256=ROOT_SHA if kind == 'root' else 'd'*64,
                source_in=[first, 30], requested_duration=[frames, 30],
                evidence=evidence(frames, prefix=prefix))


def highlight(*, gap=False, output_sha=OUTPUT_SHA):
    parts = [part(30, 60, 'one'), part(150, 30, 'two'), part(0, 15, 'meme', 'insert'), part(300, 45, 'three')]
    out = evidence(150)
    out['packets'] = [p for item in parts for p in item['evidence']['packets']]
    if gap:
        out['pts'] = [i if i < 90 else i+2 for i in range(150)]
    return build_highlights(root(), parts, output_sha, out)


class GamingLineageTests(unittest.TestCase):
    def test_actual_part_order_including_meme_and_rational_root_ranges(self):
        result = highlight()
        self.assertEqual('complete', result['state'])
        self.assertEqual([(0,60,'root',30), (60,90,'root',150), (90,105,'insert',None), (105,150,'root',300)],
            [(s['start_frame'],s['end_frame'],s['kind'],s.get('source_start_frame')) for s in result['segments']])
        self.assertEqual(ROOT_SHA, result['root_source']['sha256'])
        self.assertEqual('sha256:' + OUTPUT_SHA, result['highlights']['id'])
        self.assertEqual('not_asserted', result['approval'])
        self.assertEqual(result, highlight())

    def test_child_uses_actual_frame_plan_not_rounded_text_seconds(self):
        parent = highlight()
        result = compose_short(parent, [(50,30),(110,20)], Fraction(30), SHORT_SHA, evidence(50))
        self.assertEqual('complete', result['state'])
        self.assertEqual(list(range(50,80))+list(range(110,130)), result['highlight_frames'])
        self.assertEqual([(80,90),(150,170),(305,325)],
            [(p['start_frame'],p['end_frame']) for p in result['queue_manifest']['source_moments']])
        self.assertEqual(parent['mapping_version'], result['queue_manifest']['highlights']['version'])
        self.assertEqual([1,30], result['queue_manifest']['root_source']['timebase'])

    def test_meme_is_accounted_for_without_claiming_original_stream_frames(self):
        result = compose_short(highlight(), [(85,30)], Fraction(30), SHORT_SHA, evidence(30))
        self.assertEqual('complete', result['state'])
        self.assertEqual(15, len(result['insert_frames']))
        self.assertEqual([(175,180),(300,310)],
            [(m['start_frame'],m['end_frame']) for m in result['queue_manifest']['source_moments']])
        only_insert = compose_short(highlight(), [(90,15)], Fraction(30), SHORT_SHA, evidence(15))
        self.assertEqual('unavailable', only_insert['state'])
        self.assertEqual('no_original_source_frames', only_insert['code'])

    def test_nonzero_concat_clock_and_real_gaps_follow_existing_sampler(self):
        parent = highlight(gap=True)
        result = compose_short(parent, [(89,6)], Fraction(30), SHORT_SHA, evidence(6))
        self.assertEqual([89,89,89,90,91,92], result['highlight_frames'])
        # Missing display slots are not silently filled with invented root seconds.
        self.assertEqual([(179,180),(179,180),(179,180)],
            [(m['start_frame'],m['end_frame']) for m in result['queue_manifest']['source_moments']])

    def test_ntsc_short_sampling_is_represented_without_float_time_ranges(self):
        observed=evidence(10,fps=(30000,1001)); observed['timebase']=[1001,30000]
        result = compose_short(highlight(), [(30,10)], Fraction(30000,1001), SHORT_SHA, observed)
        self.assertEqual('complete', result['state'])
        self.assertEqual(10, len(result['highlight_frames']))
        self.assertTrue(all(isinstance(p['start_frame'],int) for p in result['queue_manifest']['source_moments']))

    def test_changed_packets_missing_frames_or_out_of_order_parts_are_unavailable(self):
        parts = [part(0,30,'a'), part(60,30,'b')]
        out = evidence(60)
        out['packets'] = parts[0]['evidence']['packets'] + parts[1]['evidence']['packets']
        out['packets'][2] = 'f'*64
        result = build_highlights(root(),parts,OUTPUT_SHA,out)
        self.assertEqual('concat_packet_mismatch', result['code'])
        out['packets'] = parts[1]['evidence']['packets'] + parts[0]['evidence']['packets']
        self.assertEqual('unavailable',build_highlights(root(),parts,OUTPUT_SHA,out)['state'])

    def test_off_grid_rate_conversion_and_trim_are_not_claimed_exact(self):
        item = part(0,30,'one'); item['source_in'] = [1,100]
        self.assertEqual('source_trim_unrepresentable', build_highlights(root(),[item],OUTPUT_SHA,item['evidence'])['code'])
        bad_root = source_record(ROOT_SHA, evidence(600, fps=(60,1)))
        self.assertEqual('unavailable',bad_root['state'])
        item = part(580,30,'one')
        self.assertEqual('source_bounds',build_highlights(root(),[item],OUTPUT_SHA,item['evidence'])['code'])

    def test_incomplete_parent_tampered_version_and_wrong_child_frame_count_block(self):
        self.assertEqual('unavailable',compose_short({'state':'unavailable'},[(0,10)],30,SHORT_SHA,evidence(10))['state'])
        parent=highlight(); parent['segments'][0]['source_start_frame']=99
        self.assertEqual('parent_lineage_changed', compose_short(parent,[(0,10)],30,SHORT_SHA,evidence(10))['code'])
        self.assertEqual('short_frame_mismatch',compose_short(highlight(),[(0,10)],30,SHORT_SHA,evidence(9))['code'])

    def test_source_bounds_and_root_cfr_evidence_are_verified(self):
        for ev in (evidence(5,offset=1),evidence(5,step=2)):
            self.assertEqual('unavailable',source_record(ROOT_SHA,ev)['state'])
        item=part(0,31,'one'); item['requested_duration']=[1,1]
        self.assertEqual('part_frame_mismatch',build_highlights(root(),[item],OUTPUT_SHA,item['evidence'])['code'])

    def test_exact_manifest_is_consumable_by_queue_without_reencoding_identity(self):
        from hinglish_publish.channel_queue_plan import propose_replenishment
        from tests.test_channel_queue_plan import snapshot, destination, policy, selection, NOW, choose
        child=compose_short(highlight(),[(0,30)],30,SHORT_SHA,evidence(30))
        manifest=child['queue_manifest']
        result=propose_replenishment(snapshot(),[manifest],selection(manifest['asset_id']),
                                     [destination()],policy(),NOW,choose)
        self.assertTrue(result['commit_ready'])
        self.assertEqual(1,len(result['new_entries']))

    def test_byte_hash_and_write_once_are_small_file_only_and_preserve_previous_record(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            path=Path(folder)/'tiny.bin';path.write_bytes(b'synthetic bytes, not a video')
            identity=file_identity(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),identity['sha256'])
            output=Path(folder)/'gaming-lineage.json'
            write_new_record(output,highlight())
            previous=output.read_bytes()
            with self.assertRaises(FileExistsError):write_new_record(output,{'state':'unavailable'})
            self.assertEqual(previous,output.read_bytes())

    def test_legacy_missing_source_lineage_is_explicit_and_no_upgrade_is_written(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            source=Path(folder)/'old.mp4';source.write_bytes(b'synthetic only')
            context=load_highlights(source)
            self.assertEqual('unavailable',context['state'])
            self.assertEqual([source],list(Path(folder).iterdir()))

    def test_short_capture_uses_measured_packets_and_preserves_parent_and_inputs(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            source=Path(folder)/'source.mp4';source.write_bytes(b'parent fixture')
            target=Path(folder)/'short.mp4';target.write_bytes(b'child fixture')
            identity=file_identity(source)
            parent=highlight(output_sha=identity['sha256']); before=copy.deepcopy(parent)
            context={'state':'complete','record':parent,'verification':identity,'path':str(source)}
            with patch('hinglish_niche.gaming_lineage.observe_video',return_value=evidence(30)):
                result=capture_short(context,source,target,[(0,30)],'30')
            self.assertEqual('complete',result['state'])
            self.assertEqual(before,parent)
            source.write_bytes(b'changed parent fixture')
            with patch('hinglish_niche.gaming_lineage.observe_video',side_effect=AssertionError('No observation after changed source')):
                result=capture_short(context,source,target,[(0,30)],'30')
            self.assertEqual('parent_media_changed',result['code'])

    def test_metadata_composition_matches_existing_source_frames_sampler(self):
        from hinglish_shorts.render import source_frames
        for parent,plan,out_fps in ((highlight(),[(20,100)],Fraction(30)),
                                     (highlight(gap=True),[(89,6)],Fraction(30)),
                                     (highlight(),[(120,20)],Fraction(30000,1001))):
            clock=parent['clock']
            frames=[SimpleNamespace(time=float(Fraction(p)*Fraction(*clock['timebase'])),index=i)
                    for i,p in enumerate(clock['pts'])]
            container=SimpleNamespace(seek=lambda *a,**k:None,decode=lambda *_:iter(frames))
            stream=SimpleNamespace(time_base=Fraction(1,30))
            actual=[f.index for f in source_frames(container,stream,plan,Fraction(30),out_fps)]
            out=evidence(sum(n for _,n in plan),fps=(out_fps.numerator,out_fps.denominator))
            out['timebase']=[out_fps.denominator,out_fps.numerator]
            result=compose_short(parent,plan,out_fps,SHORT_SHA,out)
            self.assertEqual(actual,result['highlight_frames'])

    def test_cancelled_hash_and_mutated_parent_context_do_not_assert_complete(self):
        import threading
        cancelled=threading.Event();cancelled.set()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            path=Path(folder)/'tiny.bin';path.write_bytes(b'synthetic')
            with self.assertRaises(LineageError):file_identity(path,cancelled)
            context=dict(state='complete',record=highlight(),path=str(path),verification=file_identity(path))
            with patch('hinglish_niche.gaming_lineage.observe_video',return_value=evidence(30)):
                result=capture_short(context,path,path,[(0,30)],'30')
            self.assertEqual('parent_media_changed',result['code'])

    def test_insert_changed_during_render_cannot_borrow_new_asset_identity(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            folder=Path(folder);source=folder/'source';insert=folder/'insert';out=folder/'out'
            source.write_bytes(b'root');insert.write_bytes(b'old meme');out.write_bytes(b'output')
            srcid=file_identity(source);old=file_identity(insert)
            insert.write_bytes(b'changed meme')
            context=dict(state='complete',record={**root(),'sha256':srcid['sha256']},
                         path=str(source.resolve()),verification=srcid)
            spec=dict(kind='insert',source_path=str(insert),source_in=0,requested_duration=1,
                      rendered_path=str(out),source_stamp=old['stamp'])
            result=capture_highlights(context,[spec],out)
            self.assertEqual('insert_media_changed',result['code'])

    def test_packet_observer_orders_pts_without_decoding_or_rendering(self):
        class Packet:
            def __init__(self,pts,payload):self.pts=pts;self.payload=payload;self.size=len(payload)
            def __bytes__(self):return self.payload
        stream=SimpleNamespace(base_rate=Fraction(30),average_rate=Fraction(30),time_base=Fraction(1,15360),
                               codec_context=SimpleNamespace(name='h264'))
        container=SimpleNamespace(streams=SimpleNamespace(video=[stream]),
                                  demux=lambda _:iter([Packet(512,b'b'),Packet(0,b'a'),Packet(None,b'')]))
        class Opened:
            def __enter__(self):return container
            def __exit__(self,*_):pass
        with patch('av.open',return_value=Opened()):
            result=observe_video('synthetic-never-opened.mp4')
        self.assertEqual([0,512],result['pts'])
        self.assertEqual(hashlib.sha256(b'a').hexdigest(),result['packets'][0])
        with patch('av.open',return_value=Opened()):
            with self.assertRaises(LineageError):observe_video('synthetic-never-opened.mp4',max_packets=1)

    def test_legacy_or_corrupt_sidecar_is_never_rewritten_to_complete(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            source=Path(folder)/'highlights.mp4';source.write_bytes(b'synthetic')
            sidecar=source.parent/'gaming-lineage.json';sidecar.write_text('{invalid JSON','utf-8')
            before=sidecar.read_bytes()
            self.assertEqual('unavailable',load_highlights(source)['state'])
            self.assertEqual(before,sidecar.read_bytes())


class ProducerLineageFixtureTests(unittest.TestCase):
    """Producer plumbing with synthetic observations; no model or actual render."""
    def test_gaming_renderer_collects_real_part_order_without_changing_commands(self):
        from hinglish_niche.gaming import render
        from hinglish_cut.model import Media
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            folder=Path(folder);source=folder/'source.mp4';meme=folder/'meme.mp4'
            source.write_bytes(b'synthetic');meme.write_bytes(b'synthetic meme')
            video=SimpleNamespace(path=str(source),duration=1.5,width=1280,height=720,fps=30,channels=2)
            moments=[dict(start=i*5,end=i*5+1,kind='funny') for i in range(3)]
            collected=[]; commands=[]
            def fake_run(command,**kwargs):
                commands.append(command)
                Path(command[-1]).write_bytes(b'synthetic encoded fixture')
            def fake_probe(path):
                return Media(Path(path).stem,str(path),1,'30',1280,720,2,48000)
            with patch('hinglish_niche.gaming.approved_memes',return_value=[dict(path=str(meme),tags=['funny'])]), \
                 patch('hinglish_niche.gaming.open_video',return_value=video), \
                 patch('hinglish_niche.gaming.ffmpeg_path',return_value='never-launched-ffmpeg'), \
                 patch('hinglish_niche.gaming.subprocess.run',side_effect=fake_run), \
                 patch('hinglish_cut.media.probe',side_effect=fake_probe), \
                 patch('hinglish_cut.xml_export.export_xml'):
                target,receipts=render(folder,video,moments,folder,progress=lambda _:None,lineage_parts=collected)
            self.assertEqual(['root','root','root','insert'],[p['kind'] for p in collected])
            self.assertEqual([0,5,10,0],[p['source_in'] for p in collected])
            self.assertEqual(1,len(receipts))
            self.assertEqual(5,len(commands))
            self.assertEqual('copy',commands[-1][commands[-1].index('-c')+1])

    def test_short_producer_passes_actual_frame_facts_to_lineage_capture(self):
        from hinglish_shorts.pipeline import build_short
        from hinglish_shorts.settings import ShortsSettings
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            folder=Path(folder)
            video=SimpleNamespace(path=str(folder/'highlight.mp4'),width=1280,height=720)
            context={'state':'unavailable','code':'synthetic-test'}
            item=dict(index=1,title='Synthetic',text='test',pieces=[[1.01,2.02]])
            facts=dict(frames=[(30,30)],fps='30',layers={},thumb='fixture.jpg')
            with patch('hinglish_shorts.pipeline.cap_padding',return_value=[(1.01,2.02)]), \
                 patch('hinglish_shorts.pipeline.render_short',return_value=facts), \
                 patch('hinglish_shorts.pipeline.export_short_xml',return_value=folder/'fixture.xml'), \
                 patch('hinglish_niche.gaming_lineage.capture_short',return_value={'state':'unavailable','code':'fixture'}) as capture:
                result=build_short(folder,folder,video,[],item,ShortsSettings(look='face'),
                                   progress=lambda _:None,source_lineage=context)
            self.assertEqual([(30,30)],capture.call_args.args[3])
            self.assertIs(context,capture.call_args.args[0])
            self.assertEqual('fixture',result['lineage']['code'])

    def test_new_gaming_run_saves_the_observed_record_in_both_new_receipts(self):
        from hinglish_niche.gaming import run
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            folder=Path(folder);source=folder/'source.mp4';source.write_bytes(b'synthetic source')
            previous=folder/'old-project.json';previous.write_bytes(b'preserve this old project')
            moments=[dict(start=0,end=1,kind='funny',title='Fixture',score=8,reason='Synthetic fixture')]
            brain=SimpleNamespace(close=lambda:None)
            parent=highlight();source_context={'state':'complete','record':root()}
            def fake_render(root_path,video,picked,target_folder,memes,progress,*,lineage_parts,device):
                target=target_folder/'GAMING_HIGHLIGHTS.mp4';target.write_bytes(b'synthetic render fixture')
                lineage_parts.append({'kind':'root','source_path':str(source)})
                return target,[]
            with patch('hinglish_niche.gaming.open_video',side_effect=[SimpleNamespace(path=str(source),duration=20),SimpleNamespace(duration=5,channels=2)]), \
                 patch('hinglish_niche.gaming.signals',return_value={}), \
                 patch('hinglish_niche.gaming.transcribe',return_value=[]), \
                 patch('hinglish_niche.gaming.open_brain',return_value=brain), \
                 patch('hinglish_niche.gaming.candidates',return_value=moments), \
                 patch('hinglish_niche.gaming.render',side_effect=fake_render), \
                 patch('hinglish_niche.gaming_lineage.capture_source',return_value=source_context), \
                 patch('hinglish_niche.gaming_lineage.capture_highlights',return_value=parent) as capture:
                run(folder,source,minutes=1,progress=lambda _:None)
            project_file=next((folder/'output'/'gaming').rglob('gaming-project.json'))
            self.assertEqual(parent,json.loads(project_file.read_text('utf-8'))['lineage'])
            self.assertEqual(parent,json.loads((project_file.parent/'gaming-lineage.json').read_text('utf-8')))
            self.assertIs(source_context,capture.call_args.args[0])
            self.assertEqual('root',capture.call_args.args[1][0]['kind'])
            self.assertEqual(b'preserve this old project',previous.read_bytes())


if __name__=='__main__':unittest.main()
