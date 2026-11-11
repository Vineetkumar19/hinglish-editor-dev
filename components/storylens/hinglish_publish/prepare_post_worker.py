"""One native preparation stage. Owns no queue, accounts, authorization or upload."""
import argparse
import json
import os
from pathlib import Path


def main(argv=None):
    # Set inside the -E interpreter before NumPy/PyTorch/native imports.
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text('utf-8'))
    from hinglish_app.durable_json import write
    from .prepare_post_runtime import LocalRuntime
    folder = args.request.parent
    def progress(message):
        write(folder / 'progress.json', {'message': str(message)})
    from hinglish_cut.gpu_lock import gpu_lock
    # Keep native ASR/render and model residency checks in one owning process.
    # Ollama's nested GPU guard is reentrant in this thread, never in its parent.
    progress('Waiting for the shared GPU slot')
    with gpu_lock(request['root']):
        progress('GPU slot reserved; starting the saved stage')
        result = LocalRuntime(request['root']).stage(request['stage'], request['draft'], progress)
    write(folder / 'result.json', result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
