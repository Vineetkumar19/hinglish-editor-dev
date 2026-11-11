"""Controlled local-model writing check; never calls a publishing provider."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from hinglish_publish import metadata
    from hinglish_visuals.brain import open_brain
    from hinglish_niche.profiles import Profiles,use
    folder=ROOT/'output/validation/publishing-content-only-memory'
    actual=open_brain(ROOT,'ollama')
    class CheckBrain:
        name=actual.name
        def json(self,system,data,schema,**kwargs):
            return actual.json(system,data,schema,max_tokens=800,think=False)
        def close(self):actual.close()
    transcript='This video looks back at Mumbai Indians during the 2020 IPL season and the team journey. It discusses Rohit Sharma and the Mumbai Indians squad. No specific scores, match results or statistics are provided in this input.'
    notes='Private Storylens upload test for Fantasy Legends. The 90-second upload checks the channel connection, routing and playback.'
    with use(Profiles(ROOT).context('cricket')),patch('hinglish_visuals.brain.open_brain',return_value=CheckBrain()):
        output,origin=metadata.generate(ROOT,folder/'controlled-writing-input.mp4',transcript=transcript,notes=notes)
    words=json.dumps(output,ensure_ascii=False).casefold()
    forbidden=('storylens','fantasy legends','private','upload test','uploadtest','90-second','90 second','channel connection','routing','playback','creator-supplied')
    failures=[value for value in forbidden if value in words]
    assert not failures,failures
    assert 'mumbai indians' in words and '2020' in words
    receipt={'passed':True,'scope':'Controlled writing fixture, not a transcription or real upload.',
             'model':origin,'transcript':transcript,'production_notes_to_exclude':notes,'output':output,
             'operational_text_absent':True,'weight_training_performed':False}
    (folder/'live-model-check.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__':main()
