"""Offline collection/receipt contracts; these are not Adobe acceptance tests."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from hinglish_photos.editor_plugin import prepare, accept_receipt
from hinglish_photos.service import PhotoService
from tests import test_photo_collection_service as fixtures
from tests.test_photo_collector import ROOT, picture, png


class PhotoBatchContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tmp', prefix='photo-batch-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(ROOT / 'tmp'))
        self.service, self.screenshot, self.fetch_calls = fixtures.CollectionServiceTests().make_service(self.root)
        self.service.importer = self.forbidden_live_action

    @staticmethod
    def forbidden_live_action(*args, **kwargs):
        raise AssertionError('This fixture must not call Adobe, inference, or a live source.')

    def collect(self, name='Batch one', *, different_input=False, previews=True):
        data = self.screenshot
        if different_input:
            with Image.open(io.BytesIO(data)) as image:
                image.putpixel((899, 299), (21, 22, 23))
                data = png(image)
        upload = self.service.upload(data)
        job = self.service.start({'upload_id': upload['upload_id'], 'name': name,
                                  'min_edge': 0, 'previews': previews})
        self.service.wait(job['id'], 10)
        result = self.service.snapshot(job['id'])
        self.assertEqual(result['status'], 'done', result.get('error'))
        return result

    def project(self, host):
        return str(self.root / ('owner.aep' if host == 'aftereffects' else 'owner.prproj'))

    def fake_receipt(self, manifest, number, *, host='premiere'):
        """Numbers originate in this mock host, not in the Python adapter."""
        numeric_folder = 100 + number
        return {
            'status': 'done', 'host': host, 'collection_id': manifest['id'],
            'project': {'path': self.project(host), 'root': 0 if host == 'aftereffects' else 'fixture-root',
                        'name': Path(self.project(host)).name},
            'folder': {'id': numeric_folder if host == 'aftereffects' else f'{numeric_folder:08x}',
                       'name': f'Screenshot {number}', 'parent': 'Images', 'parent_id': 'fixture-images'},
            'imported': [{'photo_id': row['id'], 'id': numeric_folder * 100 + row['id']
                          if host == 'aftereffects' else f'{numeric_folder * 100 + row["id"]:08x}',
                          'path': row['path'], 'origin': row['origin']}
                         for row in manifest['photos']],
            'upgraded': [], 'already_present': [],
            'original_count': sum(row['origin'] == 'original' for row in manifest['photos']),
            'preview_count': sum(row['origin'] == 'screenshot-preview' for row in manifest['photos']),
        }

    def accepted_batch(self, number, *, host='premiere', different_input=False):
        job = self.collect(f'Batch {number}', different_input=different_input)
        manifest = prepare(self.service, job['id'], host, {'project_id': self.project(host)})
        receipt = self.fake_receipt(manifest, number, host=host)
        accept_receipt(self.service, job['id'], host, receipt)
        return job, manifest, receipt

    def test_two_independent_batches_keep_separate_receipts_and_retry_associations(self):
        first, manifest_one, receipt_one = self.accepted_batch(1)
        second, manifest_two, receipt_two = self.accepted_batch(2, different_input=True)
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotEqual(first['source_hash'], second['source_hash'])
        self.assertNotEqual(first['output_folder'], second['output_folder'])
        self.assertTrue(set(manifest_one['paths']).isdisjoint(manifest_two['paths']))
        source = Path(manifest_one['photos'][0]['path'])
        before = source.read_bytes()
        self.service.retry(first['id'])
        self.service.wait(first['id'], 10)
        for job, receipt in ((first, receipt_one), (second, receipt_two)):
            with self.subTest(batch=job['id']):
                again = prepare(self.service, job['id'], 'premiere', {'project_id': self.project('premiere')})
                self.assertEqual(again['folder_id'], receipt['folder']['id'])
                self.assertEqual(again['expected'], receipt['project'])
                self.assertEqual(self.service.snapshot(job['id'])['native_receipts']['premiere']['folder'], receipt['folder'])
        self.assertEqual(source.read_bytes(), before)

    def test_original_bytes_dimensions_and_provenance_are_distinct_from_labelled_preview(self):
        job = self.collect()
        manifest = prepare(self.service, job['id'], 'premiere', {'project_id': self.project('premiere')})
        rows = {row['id']: row for row in manifest['photos']}
        original = Path(rows[1]['path'])
        self.assertEqual(original.read_bytes(), png(picture(3)))
        with Image.open(original) as image:
            self.assertEqual(image.size, (640, 420))
        self.assertEqual(rows[1]['origin'], 'original')
        self.assertEqual(rows[3]['origin'], 'screenshot-preview')
        preview = Path(rows[3]['path'])
        self.assertTrue(preview.is_relative_to(Path(job['output_folder']) / 'previews'))
        source_row = next(row for row in job['photos'] if row['id'] == 3)
        x, y, width, height = source_row['box']
        with Image.open(io.BytesIO(self.screenshot)) as screenshot, Image.open(preview) as image:
            self.assertEqual(image.size, (width, height))
            self.assertEqual(image.convert('RGB').tobytes(), screenshot.convert('RGB').crop((x, y, x + width, y + height)).tobytes())
        saved = self.service.snapshot(job['id'])
        confirmed = next(row for row in saved['photos'] if row['id'] == 1)
        self.assertEqual(confirmed['source_url'], 'https://photos.example/original.png')
        self.assertEqual(confirmed['source_page'], 'https://publisher.example/story')
        self.assertIn('unverified', confirmed['license'])
        self.assertEqual(saved['counts']['previews'], 1)
        self.assertTrue(all(url.startswith('https://photos.example/') for url in self.fetch_calls))

    def test_both_hosts_receipts_survive_a_new_service_instance(self):
        job = self.collect()
        expected = {}
        for host in ('aftereffects', 'premiere'):
            manifest = prepare(self.service, job['id'], host, {'project_id': self.project(host)})
            receipt = self.fake_receipt(manifest, 1, host=host)
            result = accept_receipt(self.service, job['id'], host, receipt)
            expected[host] = result['native_receipts'][host]
            self.assertEqual(json.loads(Path(expected[host]['receipt']).read_text('utf8')), receipt)
        reopened = PhotoService(self.root, analyser=self.forbidden_live_action,
                                fetcher_factory=self.forbidden_live_action)
        reopened.importer = self.forbidden_live_action
        self.assertEqual(reopened.snapshot(job['id'])['native_receipts'], expected)
        for host, receipt in expected.items():
            with self.subTest(host=host):
                manifest = prepare(reopened, job['id'], host, {'project_id': self.project(host)})
                self.assertEqual(manifest['folder_id'], receipt['folder']['id'])
                self.assertEqual(manifest['expected'], receipt['project'])

    def test_missing_original_is_rejected_before_any_receipt_is_saved(self):
        job = self.collect(previews=False)
        self.service.save(job['id'])
        row = next(row for row in self.service.snapshot(job['id'])['photos'] if row['id'] == 1)
        for directory in ('photos', 'originals'):
            path = Path(job['output_folder']) / directory / row['file']
            self.assertTrue(path.resolve().is_relative_to(self.root))
            path.unlink()
        with self.assertRaisesRegex(ValueError, 'Photo file missing'):
            prepare(self.service, job['id'], 'premiere', {'project_id': self.project('premiere')})
        self.assertFalse(self.service.snapshot(job['id']).get('native_receipts'))
        self.assertFalse((Path(job['output_folder']) / 'native-receipts').exists())

    def test_missing_labelled_preview_is_rejected_instead_of_silently_dropping_a_photo(self):
        job = self.collect()
        row = next(row for row in job['photos'] if row['id'] == 3)
        path = Path(job['output_folder']) / 'previews' / row['preview_file']
        self.assertTrue(path.resolve().is_relative_to(self.root))
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Photo file missing'):
            prepare(self.service, job['id'], 'premiere', {'project_id': self.project('premiere')})
        self.assertFalse(self.service.snapshot(job['id']).get('native_receipts'))

    def test_wrong_project_receipt_is_rejected_without_overwriting_pending_manifest(self):
        job = self.collect()
        manifest = prepare(self.service, job['id'], 'premiere', {'project_id': self.project('premiere')})
        receipt = self.fake_receipt(manifest, 1)
        receipt['project']['path'] = str(self.root / 'different.prproj')
        with self.assertRaisesRegex(ValueError, 'different project'):
            accept_receipt(self.service, job['id'], 'premiere', receipt)
        state = self.service.snapshot(job['id'])
        self.assertEqual(state['native_pending']['premiere'], manifest)
        self.assertFalse(state.get('native_receipts'))
        self.assertFalse((Path(job['output_folder']) / 'native-receipts').exists())

    def test_preview_path_cannot_escape_its_collection_preview_directory(self):
        job = self.collect()
        rows = job['photos']
        row = next(row for row in rows if row['id'] == 3)
        outside = Path(job['output_folder']) / 'outside.png'
        outside.write_bytes(png(picture(17)))
        row['preview_file'] = '../outside.png'
        self.service.update(job['id'], photos=rows)
        with self.assertRaisesRegex(ValueError, 'outside this collection'):
            prepare(self.service, job['id'], 'premiere', {'project_id': self.project('premiere')})
        self.assertFalse(self.service.snapshot(job['id']).get('native_pending'))
        self.assertEqual(outside.read_bytes(), png(picture(17)))

    def test_preview_cannot_be_reported_as_fulfilling_a_requested_original(self):
        job = self.collect()
        manifest = prepare(self.service, job['id'], 'premiere', {'project_id': self.project('premiere')})
        receipt = self.fake_receipt(manifest, 1)
        next(row for row in receipt['imported'] if row['photo_id'] == 1)['origin'] = 'screenshot-preview'
        with self.assertRaisesRegex(ValueError, 'not confirm every photo'):
            accept_receipt(self.service, job['id'], 'premiere', receipt)
        self.assertFalse(self.service.snapshot(job['id']).get('native_receipts'))

    def test_one_batch_receipt_cannot_be_attached_to_another_batch(self):
        first = self.collect()
        second = self.collect('Batch two', different_input=True)
        first_manifest = prepare(self.service, first['id'], 'premiere', {'project_id': self.project('premiere')})
        second_manifest = prepare(self.service, second['id'], 'premiere', {'project_id': self.project('premiere')})
        with self.assertRaisesRegex(ValueError, 'not confirmed'):
            accept_receipt(self.service, second['id'], 'premiere', self.fake_receipt(first_manifest, 1))
        state = self.service.snapshot(second['id'])
        self.assertEqual(state['native_pending']['premiere'], second_manifest)
        self.assertFalse(state.get('native_receipts'))

    def test_original_and_preview_links_survive_metadata_trash_restore_and_service_reopen(self):
        job, manifest, receipt = self.accepted_batch(1)
        fingerprints = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in manifest['paths']}
        self.service.archive(job['id'])
        archived = self.service.snapshot(job['id'])
        self.assertEqual(archived['archive_mode'], 'metadata')
        self.assertEqual(archived['output_folder'], job['output_folder'])
        reopened = PhotoService(self.root, analyser=self.forbidden_live_action,
                                fetcher_factory=self.forbidden_live_action)
        reopened.importer = self.forbidden_live_action
        self.assertEqual(reopened.snapshot(job['id'])['status'], 'archived')
        for path, digest in fingerprints.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)
        reopened.restore(job['id'])
        restored = prepare(reopened, job['id'], 'premiere', {'project_id': self.project('premiere')})
        self.assertEqual(restored['folder_id'], receipt['folder']['id'])
        self.assertEqual(restored['paths'], manifest['paths'])
        for path, digest in fingerprints.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
