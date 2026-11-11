from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import json

import numpy as np

from hinglish_cut.upgrade_embeddings import StagedEmbeddings


class StagedEmbeddingsTests(unittest.TestCase):
    def test_sound_search_reuses_vectors_until_the_selected_revision_changes(self):
        from hinglish_sound.brain import Brain
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
            folder = Path(folder)
            config = folder/'config.model_storage.local.json'
            def select(revision):
                config.write_text(json.dumps({'active':True,'root':str(folder),
                    'roles':{'embedding':{'ollama_model':'selected:8b','revision':revision}}}))
            select('first')
            engine = Mock(model='selected:8b', dimensions=2)
            engine.encode.side_effect = lambda texts, **kw: np.tile([1.,0.], (len(texts),1)).astype(np.float32)
            brain = object.__new__(Brain)
            brain.root, brain.embed_model = folder, 'selected:8b'
            with patch('hinglish_cut.ollama_embeddings.OllamaEmbeddings', return_value=engine), \
                 patch('hinglish_cut.model_preferences.release_ollama'):
                brain.embed(['same sound'])
                brain.embed(['same sound'])
                self.assertEqual(engine.encode.call_count, 1)
                select('new')
                brain.embed(['same sound'])
                self.assertEqual(engine.encode.call_count, 2)

    def test_resume_deduplicates_text_but_never_reuses_another_revision(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
            path = Path(folder)/'vectors.sqlite3'
            engine = Mock(model='selected:8b', dimensions=2)
            engine.encode.side_effect = lambda texts, **kw: np.tile([1.,0.], (len(texts),1)).astype(np.float32)
            cache = StagedEmbeddings(path, engine, 'first')
            self.assertEqual(cache.encode(['same', 'same']).shape, (2,2))
            engine.encode.assert_called_once_with(['same'], manage_residency=False)
            cache.close()
            engine.encode.reset_mock()
            cache = StagedEmbeddings(path, engine, 'first')
            np.testing.assert_array_equal(cache.encode(['same']), [[1.,0.]])
            engine.encode.assert_not_called()
            cache.close()
            cache = StagedEmbeddings(path, engine, 'changed')
            cache.encode(['same'])
            engine.encode.assert_called_once()
            cache.close()

    def test_changed_text_and_corrupt_vector_are_recomputed(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
            engine = Mock(model='selected:8b', dimensions=2)
            engine.encode.side_effect = lambda texts, **kw: np.tile([0.,1.], (len(texts),1)).astype(np.float32)
            cache = StagedEmbeddings(Path(folder)/'vectors.sqlite3', engine, 'revision')
            cache.encode(['old'])
            with cache.db:
                cache.db.execute('UPDATE vectors SET vector=?', (np.array([float('nan'),0.],np.float32).tobytes(),))
            engine.encode.reset_mock()
            cache.encode(['old','changed'])
            engine.encode.assert_called_once_with(['old','changed'], manage_residency=False)
            cache.close()


if __name__ == '__main__': unittest.main()
