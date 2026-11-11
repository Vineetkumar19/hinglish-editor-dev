"""Resumable, revision-specific staging of embeddings without changing live data."""
import hashlib
from pathlib import Path
import sqlite3

import numpy as np


class StagedEmbeddings:
    def __init__(self, path, encoder, revision):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.encoder, self.revision = encoder, revision
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector BLOB NOT NULL)')

    def key(self, text):
        value = self.encoder.model + '\0' + self.revision + '\0passage\0' + text
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def encode(self, texts):
        keys = [self.key(text) for text in texts]
        found, missing = {}, {}
        for key, text in zip(keys, texts):
            if key in found or key in missing:
                continue
            row = self.db.execute('SELECT vector FROM vectors WHERE key=?', (key,)).fetchone()
            try:
                vector = np.frombuffer(row[0], np.float32) if row else None
            except ValueError:
                vector = None
            if (vector is not None and vector.shape == (self.encoder.dimensions,)
                    and np.isfinite(vector).all() and .99 < np.linalg.norm(vector) < 1.01):
                found[key] = vector
            else:
                missing[key] = text
        if missing:
            vectors = self.encoder.encode(list(missing.values()), manage_residency=False)
            if vectors.shape != (len(missing), self.encoder.dimensions):
                raise ValueError('Staged embeddings have an invalid shape')
            if not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=.01):
                raise ValueError('Staged embeddings are not finite normalized vectors')
            with self.db:
                for key, vector in zip(missing, vectors):
                    vector = np.asarray(vector, np.float32)
                    self.db.execute('INSERT OR REPLACE INTO vectors VALUES (?,?)', (key, vector.tobytes()))
                    found[key] = vector
        return np.asarray([found[key] for key in keys], np.float32).reshape((-1, self.encoder.dimensions))

    def close(self):
        self.db.close()
        self.encoder.close()
