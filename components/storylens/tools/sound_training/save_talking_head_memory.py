"""Append owner-requested sound guidance without replacing prior reference knowledge."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/sound-training/20261030-revision2'
def main():
    path=ROOT/'hinglish_app/knowledge/sound_design_teaching.json'
    backup=OUT/'sound_design_teaching.before.json'
    if not backup.exists():backup.write_bytes(path.read_bytes())
    data=json.loads(path.read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'references/manifest.json').read_text())
    existing={s['id'] for s in data['sources']}
    for row in manifest:
        rid='talking-head-'+row['id']+'-20261030'
        if rid not in existing:
            data['sources'].append(dict(id=rid,name=Path(row['path']).stem,seconds=row['duration'],
                source=row['path'],sha256=row['sha256'],reviewed=False,transcription_complete=False,
                evidence=str(OUT/'references'/row['id']),
                review_scope='All frames decoded; visual overview inspected; 2-second mixed-audio CLAP hypotheses, not an isolated-stem audition. Exact SFX identity remains unverified.'))
    lessons=[
      dict(id='talking-head-selective-accents-20261030',topics=['talking-head','typography','subtitles','letters','pop','captions','graphics'],
        principle='Make a talking-head sound plan support speech and visual hierarchy; do not click every caption word.',
        when='Word reveals, headline entrances, UI inserts and spoken emphasis in creator reels.',
        how='Identify a few meaningful events, then choose complementary motion, contact or tonal roles. Let routine subtitles remain quiet; vary treatments by narrative purpose.',
        avoid='A repeated four-effect template, mandatory five-layer stacks, or replacing physical/environment sounds with UI clicks.'),
      dict(id='talking-head-duration-20261030',topics=['talking-head','typography','tail','decay','duration','swoosh','letters'],
        principle='An entrance may be brief while its movement or musical decay continues naturally.',
        when='Slides, glows, letter bursts, title landings and soft transitions.',
        how='Align the meaningful audible onset or peak, follow the actual motion and retain useful tails, including one to three seconds where appropriate. Check the next phrase for masking.',
        avoid='Uniform 0.1/0.2-second cuts, file-start alignment without checking leading silence, or effects louder than the spoken message.'),
      dict(id='talking-head-emotional-variation-20261030',topics=['talking-head','joke','comedy','reflective','explanation','reel'],
        principle='One reel can need several emotional treatments while retaining a coherent sonic palette.',
        when='A joke changes to a technical explanation, meaningful pause or personal comment.',
        how='Use a fitting comic response selectively, precise graphic accents for explanation and quieter sustained support or negative space for reflection. Preserve approved music and useful source audio once.',
        avoid='Changing only filenames while repeating the same stack; adding another song over existing music; treating silence as missing work.')
    ]
    for row in lessons:
        row['evidence']=[dict(source='owner-direction-20261030',kind='Teacher design guidance; new-reference audio identities remain hypotheses',
            files=[r['sha256'] for r in manifest],measured_artifacts='output/sound-training/20261030-revision2/references')]
        if row['id'] not in {x['id'] for x in data['lessons']}:data['lessons'].append(row)
    limitation='The three 30 October talking-head references have mixed-audio classifier hypotheses, not verified isolated SFX identities or exact layer counts. New cards are teacher guidance, not claimed transcriptions.'
    if limitation not in data['limitations']:data['limitations'].append(limitation)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved three talking-head sound cards; preserved all prior cards and source records.')
if __name__=='__main__':main()
