"""Reuse the installed isolated NF4 trainer without changing Sound artifacts."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.sound_training import train as engine
from tools.publishing_training.curriculum import OUT

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',default='20261030-v1')
    parser.add_argument('--parent')
    parser.add_argument('--epochs',type=int,default=2,choices=range(1,9))
    args=parser.parse_args()
    home=ROOT/'output/publishing-training'
    OUT=(home/args.run).resolve()
    if OUT.parent!=home.resolve():raise ValueError('Use a direct publishing-training run folder')
    parent=(home/args.parent/'adapter').resolve() if args.parent else None
    if parent and parent.parent.parent!=home.resolve():raise ValueError('Use a saved publishing adapter')
    engine.OUT=OUT
    engine.DEFAULTS.update(num_train_epochs=args.epochs,learning_rate=5e-5 if parent else 3e-5,max_seq_length=2048 if parent else 1024)
    engine.EVALUATION_LIMIT=0  # Separate full-schema comparison evaluates all held-out cases.
    try:engine.run('train',initial_adapter=parent)
    except BaseException as error:
        engine.status('stopped_with_error',error_type=type(error).__name__,error=str(error),mode='train')
        raise
