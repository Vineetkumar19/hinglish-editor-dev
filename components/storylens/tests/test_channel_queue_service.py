"""Temporary queue + fake account readers and tiny synthetic files only.

No real account selection, authorization, media semantics, providers or workers.
"""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from hinglish_publish.service import Publisher
from hinglish_publish.channel_queue_plan import ProposalError
from tests.test_channel_queue_plan import asset,selection,policy,choose,NOW


class ChannelQueueServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='cache');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.publisher=Publisher(self.root,providers={'youtube':Mock(),'instagram':Mock()})
        self.accounts={'youtube':{'connected':True,'id':'yt-gaming'},'instagram':{'connected':True,'id':'ig-gaming'}}
        self.publisher.accounts=Mock(side_effect=lambda profile:copy.deepcopy(self.accounts))
        self.pair={'youtube':'yt-gaming','instagram':'ig-gaming'}
        self.candidate=asset(0);file=self.root/'output/shorts/synthetic.mp4';file.parent.mkdir(parents=True);file.write_bytes(b'SYNTHETIC MEDIA NOT A REAL VIDEO')
        self.candidate['content_sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
        meta={'title':'A gaming highlight','description':'A synthetic fixture description.','instagram_caption':'A highlight. #Gaming','tags':['Gaming']}
        self.media={self.candidate['asset_id']:{'verified':True,'asset':copy.deepcopy(self.candidate),
            'content_sha256':self.candidate['content_sha256'],'video':str(file),'metadata':{'youtube':meta,'instagram':meta},'visibility':'public'}}

    def args(self):
        # Explicit IDs only; the service verifies them against this profile.
        dests=[dict(profile_id='gaming',platform=p,account_id=a,connection_ref=p+'-gaming',verified=True) for p,a in self.pair.items()]
        return dict(profile='gaming',pair=self.pair,finished_candidates=[self.candidate],selection=selection('short-0'),
                    policy=policy(*dests),media=self.media,now=NOW)

    def plan(self):return self.publisher.channel_queue_proposal(**self.args(),slot_choices=choose)

    def assert_code(self,code,fn):
        with self.assertRaises(ProposalError) as caught:fn()
        self.assertEqual(caught.exception.code,code)

    def test_missing_pair_requires_explicit_account_selection_and_writes_nothing(self):
        args=self.args();args['pair']={'youtube':'yt-gaming'}
        self.assert_code('needs_account_selection',lambda:self.publisher.channel_queue_proposal(**args,slot_choices=choose))
        self.assertEqual(self.publisher.store.list(),[])

    def test_paired_prepare_commit_is_draft_only_and_repeat_is_idempotent(self):
        proposal=self.plan();receipt=self.publisher.channel_queue_commit(proposal,**self.args())
        jobs=self.publisher.store.list();self.assertEqual(len(jobs),2)
        self.assertTrue(all(j['status']=='draft' and j['execution_authorized'] is False and not j['remote'] for j in jobs))
        self.assertIsNone(self.publisher.store.claim(NOW.timestamp()+999999))
        again=self.publisher.channel_queue_commit(proposal,**self.args())
        self.assertTrue(again['replayed']);self.assertEqual(receipt['receipt'],again['receipt'])
        self.assertEqual(jobs,self.publisher.store.list())

    def test_current_profile_pair_change_blocks_commit_without_retargeting(self):
        proposal=self.plan();self.accounts['instagram']['id']='different-instagram'
        self.assert_code('account_binding_changed',lambda:self.publisher.channel_queue_commit(proposal,**self.args()))
        self.assertEqual(self.publisher.store.list(),[])

    def test_changed_finished_media_is_not_committed(self):
        proposal=self.plan();Path(self.media['short-0']['video']).write_bytes(b'CHANGED')
        self.assert_code('media_identity_changed',lambda:self.publisher.channel_queue_commit(proposal,**self.args()))
        self.assertEqual(self.publisher.store.list(),[])

    def test_authorization_rechecks_saved_destination_instead_of_rebinding(self):
        self.publisher.channel_queue_commit(self.plan(),**self.args());before=self.publisher.store.list()
        self.accounts['instagram']['id']='different-instagram'
        self.assert_code('account_binding_changed',lambda:self.publisher.authorize({'ids':[j['id'] for j in before],
            'authorize':True,'made_for_kids':False,'synthetic_media':False}))
        self.assertEqual(before,self.publisher.store.list())

    def test_fake_authorization_marks_bound_rows_without_starting_any_provider(self):
        self.publisher.channel_queue_commit(self.plan(),**self.args());jobs=self.publisher.store.list()
        self.publisher.authorize({'ids':[j['id'] for j in jobs],'authorize':True,'made_for_kids':False,'synthetic_media':False})
        after=self.publisher.store.list()
        self.assertTrue(all(j['status']=='ready' and j['execution_authorized'] is True for j in after))
        self.assertEqual({j['platform']:j['account_id'] for j in after},self.pair)
        for provider in self.publisher.providers.values():provider.assert_not_called()
        self.publisher.accounts.assert_called_with('gaming')

