import importlib.util
import tempfile
import unittest
from pathlib import Path


def module():
    spec = importlib.util.spec_from_file_location('documentary_copy', Path(__file__).resolve().parents[1] / 'tools/consolidate_documentary_templates.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class DocumentaryCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dest = self.root / 'LatestUniqueTemplete'
        self.dest.mkdir()

    def file(self, relative, content=b'project'):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return p

    def test_exact_duplicates_are_skipped_but_different_versions_are_retained(self):
        m = module()
        self.file('LatestUniqueTemplete/History/History.aep', b'old')
        self.file('other/History/History.aep', b'old')
        self.file('other/History/History copy 22.x.aep', b'new')
        plan = m.plan(self.root)
        self.assertEqual(plan['unique_projects'], 2)
        self.assertEqual(len(plan['missing_projects']), 1)
        self.assertEqual(len(plan['packages']), 1)

    def test_autosaves_and_mac_metadata_are_not_new_templates(self):
        m = module()
        self.file('pack/._Title.aep')
        self.file('pack/Adobe After Effects Auto-Save/Title auto-save 1.aep')
        self.file('pack/Title.aep')
        self.assertEqual(m.plan(self.root)['unique_projects'], 1)

    def test_copy_keeps_entire_pack_and_hash_verifies_without_touching_originals(self):
        m = module()
        project = self.file('source/Logo/AE/Logo.aep')
        asset = self.file('source/Logo/Assets/texture.png', b'pixels')
        self.file('source/Logo/Help.txt', b'help')
        plan = m.plan(self.root)
        receipt = m.apply(plan)
        self.assertEqual(receipt['copied_packages'], 1)
        copied = Path(plan['packages'][0]['destination'])
        self.assertEqual((copied / 'AE/Logo.aep').read_bytes(), project.read_bytes())
        self.assertEqual((copied / 'Assets/texture.png').read_bytes(), asset.read_bytes())
        self.assertTrue(project.exists())
        self.assertEqual(m.plan(self.root)['missing_projects'], [])

    def test_existing_destination_collision_is_preserved(self):
        m = module()
        existing = self.file('LatestUniqueTemplete/History/note.txt', b'owner file')
        self.file('outside/History/History.aep', b'new')
        plan = m.plan(self.root)
        self.assertNotEqual(Path(plan['packages'][0]['destination']), existing.parent)
        m.apply(plan)
        self.assertEqual(existing.read_bytes(), b'owner file')

    def test_identical_project_with_different_assets_is_kept_as_a_pack_variant(self):
        m = module()
        self.file('LatestUniqueTemplete/History/History.aep', b'same project')
        self.file('LatestUniqueTemplete/History/Footage/picture.png', b'original picture')
        self.file('source/History/History.aep', b'same project')
        self.file('source/History/Footage/picture.png', b'different picture')
        plan = m.plan(self.root)
        self.assertEqual(plan['missing_projects'], [])
        self.assertEqual(len(plan['packages']), 1)
        self.assertEqual(plan['packages'][0]['reason'], 'different_assets')
        m.apply(plan)
        self.assertEqual(m.plan(self.root)['packages'], [])

    def test_after_effects_folder_with_own_footage_does_not_absorb_neighboring_packs(self):
        m = module()
        self.file('LatestUniqueTemplete/Title/Title.aep', b'same')
        self.file('LatestUniqueTemplete/Title/(Footage)/image.png', b'picture')
        self.file('source/After Effects/Title.aep', b'same')
        self.file('source/After Effects/(Footage)/image.png', b'picture')
        self.file('source/Unrelated/render.mov', b'unrelated')
        self.assertEqual(m.plan(self.root)['packages'], [])

    def test_changed_source_and_destination_escape_are_refused(self):
        m = module()
        source = self.file('outside/History/History.aep')
        plan = m.plan(self.root)
        source.write_bytes(b'changed after planning')
        with self.assertRaisesRegex(ValueError, 'changed'):
            m.apply(plan)
        plan = m.plan(self.root)
        plan['packages'][0]['destination'] = str(self.root / 'wrong-folder')
        with self.assertRaisesRegex(ValueError, 'destination'):
            m.apply(plan)


if __name__ == '__main__':
    unittest.main()
