"""Four explicitly authorized private uploads, using local Qwen and real publisher tools.

Preparation and remote checkpoints are durable. Re-running never retries an
ambiguous upload or creates a duplicate for a saved YouTube ID.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FOLDER = ROOT / 'output/validation/youtube-two-channel-local-demo-20261019'
CHANNELS = {'cricket': 'UCISO1Vfw20A6Tlb2xMGQqGg', 'gaming': 'UCtc3vpF9QPHAM7lTYCCulyg'}
SOURCES = [
    ('cricket', 'short', 20, 15, r'D:/Editing/documentry edit/final videos/final shorts/Mi 2024 shorts/1.mp4'),
    ('cricket', 'long', 120, 90, r'D:/Editing/documentry edit/final videos/final videos/mi2020 final.mp4'),
    ('gaming', 'short', 20, 15, r'D:/Editing/documentry edit/final videos/final shorts/Mi 2024 shorts/2.mp4'),
    ('gaming', 'long', 150, 90, r'D:/Editing/documentry edit/final videos/final videos/kkr final.mp4'),
]


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), 'utf-8')
    temp.replace(path)


def log(text):
    print(text, flush=True)


def connections():
    from hinglish_publish.providers import youtube_client
    result = {}
    for profile, expected in CHANNELS.items():
        client, stored = youtube_client(ROOT, profile)
        channels = client.channels().list(part='snippet', mine=True).execute()['items']
        assert len(channels) == 1 and channels[0]['id'] == expected == stored['channel_id']
        result[profile] = {'id': expected, 'name': channels[0]['snippet']['title'],
                           'handle': channels[0]['snippet'].get('customUrl')}
    save(FOLDER / 'channels.json', result)
    return result


def prepare():
    import av
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import release_ollama
    from hinglish_shorts.source import open_video, transcribe
    from hinglish_publish.metadata import SCHEMA, SYSTEM, CONTENT_RULE, SEO_RULE, ENGLISH_RULE, validate
    from hinglish_publish.memory import CreatorMemory
    from hinglish_publish.store import fingerprint
    from hinglish_visuals.brain import open_brain

    prepare_speech_batch()
    manifest_path = FOLDER / 'prepared.json'
    manifest = json.loads(manifest_path.read_text('utf-8')) if manifest_path.exists() else {'clips': []}
    for profile, kind, offset, seconds, source in SOURCES:
        name = profile + '-' + kind
        if any(c['name'] == name for c in manifest['clips']):
            continue
        target = FOLDER / (name + '.mp4')
        transcript_path = target.with_suffix('.txt')
        with gpu_lock(ROOT):
            if not target.exists():
                log('Extracting ' + name + ' with RTX NVENC')
                command = [get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                           '-ss', str(offset), '-i', source, '-t', str(seconds), '-map', '0:v:0', '-map', '0:a:0',
                           '-vf', 'scale=1080:1920' if kind == 'short' else 'scale=1920:1080',
                           '-r', '30', '-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '25', '-b:v', '0',
                           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(target)]
                subprocess.run(command, check=True)
            facts = open_video(target)
            assert abs(facts.duration - seconds) < .2
            assert (facts.height > facts.width) == (kind == 'short')
            if not transcript_path.exists():
                release_ollama(ROOT)
                log('Transcribing ' + name + ' on CUDA')
                words = transcribe(ROOT, facts, device='cuda', progress=log)
                transcript_path.write_text(' '.join(w.text for w in words), 'utf-8')
            transcript = transcript_path.read_text('utf-8')
            assert len(transcript.strip()) > 15
            model_path = FOLDER / (name + '-local-metadata.json')
            if model_path.exists():
                record = json.loads(model_path.read_text('utf-8'))
            else:
                log('Qwen is writing content-based title and description for ' + name)
                brain = open_brain(ROOT, 'ollama', progress=log)
                try:
                    metadata = validate(brain.json(SYSTEM + '\n' + CONTENT_RULE + '\n' + SEO_RULE + '\n' + ENGLISH_RULE,
                        {'transcript': transcript, 'creator_preferences': CreatorMemory(ROOT, profile).writing_context(),
                         'creator_notes': 'Describe this actual cricket excerpt in English. The destination account does not change the topic. Write a substantial useful description with relevant hashtags, but never invent events, results, dates or statistics. This is an excerpt, so do not promise a complete documentary. Omit operational/testing/visibility language.'},
                        SCHEMA, max_tokens=2400, think=False))
                    record = {'brain': brain.name, 'think': False, 'metadata': metadata}
                    save(model_path, record)
                finally:
                    brain.close()
            with av.open(str(target)) as media:
                media.seek(3 * av.time_base)
                for frame in media.decode(video=0):
                    if frame.time >= 3:
                        frame.to_image().save(FOLDER / (name + '-preview.jpg'))
                        break
        clip = {'name': name, 'profile': profile, 'kind': kind, 'video': str(target), 'source': source,
                'offset': offset, 'duration': facts.duration, 'width': facts.width, 'height': facts.height,
                'sha256': fingerprint(target), 'brain': record['brain'], 'metadata': record['metadata']}
        manifest['clips'].append(clip)
        save(manifest_path, manifest)
        log('Prepared ' + name + ': ' + record['metadata']['title'])
    log('All four clips and local-model drafts are prepared. Review before upload.')


def prepare_speech_batch():
    """Share one ASR load across clips; metadata does not need word alignment."""
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import release_ollama
    from hinglish_cut.media import read_audio
    from hinglish_semantic.core import SemanticSettings
    from hinglish_semantic.speech import speech_engine
    from hinglish_cut.recognition_quality import checked_transcript
    with gpu_lock(ROOT):
        release_ollama(ROOT)
        settings = json.loads((ROOT / 'config.phase2.json').read_text('utf-8-sig'))
        settings.update(device='cuda', speech_backend='swift', matching_backend='word_coverage')
        engine = None
        try:
            for profile, kind, offset, seconds, source in SOURCES:
                target = FOLDER / (profile + '-' + kind + '.mp4')
                if not target.exists():
                    log('Extracting ' + target.stem + ' with RTX NVENC')
                    subprocess.run([get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                        '-ss', str(offset), '-i', source, '-t', str(seconds), '-map', '0:v:0', '-map', '0:a:0',
                        '-vf', 'scale=1080:1920' if kind == 'short' else 'scale=1920:1080',
                        '-r', '30', '-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '25', '-b:v', '0',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(target)], check=True)
                transcript_path = target.with_suffix('.txt')
                if transcript_path.exists():
                    continue
                wav = target.with_suffix('.wav')
                if not wav.exists():
                    subprocess.run([get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                        '-i', str(target), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True)
                if engine is None:
                    engine = speech_engine(SemanticSettings(**settings), ROOT)
                chunks = []
                for start in range(0, seconds, 20):
                    log('Local CUDA transcript ' + target.stem + ': ' + str(start) + '/' + str(seconds) + 's')
                    text = engine.recognize(read_audio(wav, start, min(seconds, start + 20)))
                    checked_transcript(text)
                    chunks.append(text)
                transcript_path.write_text(' '.join(chunks), 'utf-8')
        finally:
            if engine is not None:
                engine.close()


def upload():
    from hinglish_publish.providers import youtube_client
    from hinglish_publish.service import Publisher
    from hinglish_publish.store import fingerprint
    from hinglish_publish.worker_lock import acquire
    manifest = json.loads((FOLDER / 'prepared.json').read_text('utf-8'))
    assert len(manifest['clips']) == 4
    assert manifest.get('reviewed') is True, 'Review titles and descriptions against source transcripts first.'
    publisher = Publisher(ROOT)
    assert all(not publisher.settings(profile=p)['enabled'] for p in ('general', 'cricket', 'gaming'))
    channels = connections()
    receipt_path = FOLDER / 'upload-receipt.json'
    receipt = json.loads(receipt_path.read_text('utf-8')) if receipt_path.exists() else {
        'requested_visibility': 'private', 'scheduled_publishing_enabled': False,
        'channels': channels, 'uploads': [], 'started': time.time()}
    worker = acquire(ROOT)
    try:
        for clip in manifest['clips']:
            assert fingerprint(clip['video']) == clip['sha256']
            item = {**{k: clip[k] for k in ('profile','kind','video','duration','width','height','brain','metadata')},
                    'fingerprint': clip['sha256'], 'platform': 'youtube', 'visibility': 'private', 'thumbnail': '',
                    'thumbnail_fingerprint': '', 'video_url': ''}
            job_id = publisher.store.add_batch([item])[0]
            job = publisher.store.get(job_id)
            row = next((r for r in receipt['uploads'] if r['job_id'] == job_id), None)
            if row is None:
                row = {'job_id': job_id, 'name': clip['name'], 'profile': clip['profile'], 'kind': clip['kind'],
                       'title': clip['metadata']['title'], 'description': clip['metadata']['description']}
                receipt['uploads'].append(row)
                save(receipt_path, receipt)
            if job.get('remote', {}).get('id'):
                row.update(job['remote'])
                log('Reusing the accepted remote ID for ' + clip['name'] + '; no new upload.')
                continue
            assert job['status'] == 'draft', 'An upload was already attempted; inspect saved state, never retry ambiguously.'
            publisher.store.change(job_id, due=time.time())
            publisher.authorize({'ids': [job_id], 'authorize': True, 'made_for_kids': False, 'synthetic_media': False})
            publisher.store.change(job_id, expected_status=('ready',), status='uploading', attempts=1)
            job = publisher.store.get(job_id)
            assert job['visibility'] == 'private' and job['account_id'] == CHANNELS[clip['profile']]
            log('Uploading privately to ' + channels[clip['profile']]['name'] + ': ' + clip['metadata']['title'])
            config = {**publisher.settings(profile=clip['profile']), 'visibility': 'private'}
            try:
                remote, status = publisher.providers['youtube'](ROOT, config).publish(job,
                    lambda remote: publisher.store.change(job_id, remote=remote))
                publisher.store.change(job_id, status=status, remote=remote, error='')
                publisher.store.event(job_id, 'Explicit two-channel private demo: ' + remote['url'])
                row.update(remote, status=status, accepted_at=time.time())
                save(receipt_path, receipt)
                log('YouTube accepted ' + remote['url'])
            except Exception as error:
                publisher.store.change(job_id, status='needs_review', error='Private demo requires outcome review; never auto-retry.')
                row['failure_type'] = type(error).__name__
                save(receipt_path, receipt)
                raise
    finally:
        worker.close()
    verify()


def revise(model=None):
    """Local-model corrections based on operator review of the actual transcripts."""
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_publish.metadata import SCHEMA, SYSTEM, CONTENT_RULE, ENGLISH_RULE, validate
    from hinglish_visuals.brain import open_brain
    corrections = {
        'cricket-short': 'This 15-second excerpt introduces a comparison between Rohit Sharma and MS Dhoni in IPL captaincy. It then introduces Rohit and Mumbai Indians. The milestone itself is not identified in this excerpt. Do not invent a milestone, strategies, detailed analysis, or imply Dhoni was Rohit\'s predecessor at Mumbai Indians. Omit the numerical timelines because their referent is absent. A title about an IPL captaincy comparison is appropriate.',
        'cricket-long': 'This excerpt is about Mumbai Indians in IPL 2020. The narration says they beat Delhi twice in the league phase; they had five defeats, including TWO SUPER OVER LOSSES. Two heavier defeats came against Hyderabad and Rajasthan Royals. An eight-wicket defeat means the opponent won by eight wickets, not Mumbai being bowled out for eight wickets. Batting contributions were spread across players; no Mumbai player won the Orange Cap. The narrator mentions Rohit\'s powerplay starts and Trent Boult\'s new-ball bowling. Omit ALL run totals, wicket margins, Orange/Purple Cap ranks and garbled player names. Do not turn the Super Over defeats into wins or claim they only lost two matches.',
        'gaming-short': 'The garbled ASR proper name "fachindandulgar" refers to SACHIN TENDULKAR, not Hardik Pandya. This is a short historical Mumbai Indians excerpt. It says Mumbai won the match and discusses Sachin\'s good batting form early in the campaign. Omit match-award counts and unidentified season numbers. No Hardik Pandya, all-round performance, detailed match analysis or bowling claims are supported.',
        'gaming-long': 'This historical KKR excerpt discusses leadership involving Sourav Ganguly and Brendon McCullum, then Gautam Gambhir joining in 2011, Kolkata reaching the playoffs and losing the Eliminator to Mumbai Indians. It ends by introducing Sunil Narine\'s arrival in 2012. Do not claim this excerpt shows a championship win, do not add an auction price, losing-streak counts or unsupported dressing-room details. Do not repeat the source\'s potentially inaccurate mid-season-change claim. Focus on the leadership transition and playoff progress.'}
    manifest_path = FOLDER / 'prepared.json'
    manifest = json.loads(manifest_path.read_text('utf-8'))
    with gpu_lock(ROOT):
        brain = open_brain(ROOT, 'ollama', model=model or 'qwen3:8b', progress=log)
        try:
            for clip in manifest['clips']:
                reviewed_file = FOLDER / (clip['name'] + ('-14b-metadata.json' if model else '-revised-metadata.json'))
                if reviewed_file.exists():
                    record = json.loads(reviewed_file.read_text('utf-8'))
                else:
                    log('Correcting local draft against source evidence: ' + clip['name'])
                    length = '60-90 words' if clip['kind'] == 'short' else '150-210 words'
                    response = brain.json(SYSTEM + '\n' + CONTENT_RULE + '\n' + ENGLISH_RULE +
                        '\nWrite the YouTube description in ' + length + '. End it with 3-5 relevant hashtags. '
                        'Use readable paragraphs and natural subject keywords. Never invent analysis to reach a word target. '
                        'Omit numerical claims except explicitly approved years. Keep the separate Instagram caption to one short sentence and hashtags. '
                        'The reviewed source notes resolve ASR errors and are the factual authority for this excerpt.',
                        {'reviewed_source_notes': corrections[clip['name']],
                         'source_type': 'Existing cricket documentary excerpt; destination is not the subject'},
                        SCHEMA, max_tokens=1400, think=False)
                    record = {'brain': brain.name, 'operator_source_notes': corrections[clip['name']],
                              'metadata': validate(response), 'think': False}
                    save(reviewed_file, record)
                clip['metadata'] = record['metadata']
                clip['brain'] = record['brain']
                clip['operator_source_review'] = str(reviewed_file)
                save(manifest_path, manifest)
                log('Revised title: ' + clip['metadata']['title'])
        finally:
            brain.close()


def verify():
    from hinglish_publish.providers import youtube_client
    from hinglish_publish.service import Publisher
    receipt_path = FOLDER / 'upload-receipt.json'
    receipt = json.loads(receipt_path.read_text('utf-8'))
    publisher = Publisher(ROOT)
    for profile in CHANNELS:
        client, _ = youtube_client(ROOT, profile)
        rows = [r for r in receipt['uploads'] if r['profile'] == profile]
        assert len(rows) == 2 and all(r.get('id') for r in rows)
        items = client.videos().list(part='snippet,status,contentDetails,processingDetails',
                                    id=','.join(r['id'] for r in rows)).execute()['items']
        assert len(items) == 2
        for item in items:
            row = next(r for r in rows if r['id'] == item['id'])
            assert item['snippet']['channelId'] == CHANNELS[profile]
            assert item['snippet']['title'] == row['title'] and item['snippet']['description'] == row['description']
            assert item['status']['privacyStatus'] == 'private'
            assert item['status']['uploadStatus'] not in ('failed','rejected','deleted')
            row.update(privacy='private', channel_verified=True, metadata_verified=True,
                       upload_status=item['status']['uploadStatus'], duration=item['contentDetails']['duration'],
                       processing_status=item.get('processingDetails',{}).get('processingStatus'))
            publisher.store.change(row['job_id'], verification={
                'checked': time.time(), 'privacy': 'private', 'channel_verified': True, 'metadata_verified': True,
                'upload_status': row['upload_status'], 'processing_status': row['processing_status']},
                metadata_review='operator editorial review after local 9B and 14B drafts',
                upload_trigger='Explicit user request executed through the publisher demo harness')
    receipt.update(checked=time.time(), all_processed=all(r['upload_status']=='processed' for r in receipt['uploads']))
    receipt['metadata_provenance'] = 'Local Qwen 9B and 14B drafts plus explicit operator editorial corrections'
    receipt['execution'] = 'Real local publisher; final upload executed by explicit demo harness, not local-chat auto-execution'
    save(receipt_path, receipt)
    log(json.dumps(receipt, indent=2))


def approve_reviewed_copy():
    """Editorial review is explicit, separate from both saved local model drafts."""
    from hinglish_publish.metadata import validate
    edits = {
        'cricket-short': {
            'title': 'Rohit Sharma vs MS Dhoni | IPL Captaincy Comparison #Shorts',
            'description': "Rohit Sharma and MS Dhoni are the focus of this IPL captaincy comparison, which introduces a look back at Rohit's journey with Mumbai Indians.\n\nThe narration contrasts their paths before turning to Rohit and the Mumbai Indians story. For fans revisiting IPL history, this short introduction brings the conversation back to captaincy, franchise achievements and the players at the centre of that discussion.\n\n#RohitSharma #MSDhoni #MumbaiIndians #IPL #Shorts"},
        'cricket-long': {
            'title': "Mumbai Indians 2020 IPL Journey | Team Strength and Super Over Setbacks",
            'description': "Mumbai Indians' IPL 2020 journey combined strong team performances with memorable setbacks. This chapter looks at their league-stage wins over Delhi, the matches that tested them, and the contributions that made their campaign stand out.\n\nThe narration revisits Mumbai's two league wins against Delhi and contrasts that control with Super Over defeats and heavier losses against Hyderabad and Rajasthan Royals. These moments form part of the same story: a strong side still had matches where the opposition got the better of them.\n\nThe batting discussion focuses on contributions spread across the squad, rather than a single Orange Cap winner. Rohit Sharma's attacking starts in the powerplay are part of that account, alongside the runs supplied by Mumbai's other leading batters.\n\nWith the ball, the chapter turns to Trent Boult and the impact of his new-ball bowling. Together, the batting and bowling passages show how different players contributed to Mumbai Indians' season.\n\nRevisit this part of Mumbai's IPL history through the wins, defeats and shared performances discussed in the documentary.\n\n#MumbaiIndians #IPL2020 #RohitSharma #TrentBoult #CricketHistory"},
        'gaming-short': {
            'title': "Sachin Tendulkar's Batting Form for Mumbai Indians #Shorts",
            'description': "Sachin Tendulkar's batting form takes centre stage in this look back at Mumbai Indians. The narration recalls a Mumbai victory and highlights Sachin's strong touch during the early part of the campaign.\n\nThis brief chapter focuses on his contribution and the positive form Mumbai were showing at that point. It is a moment from the franchise's earlier IPL story, with the attention on Sachin's batting and the team's performance.\n\n#SachinTendulkar #MumbaiIndians #IPL #CricketHistory #Shorts"},
        'gaming-long': {
            'title': 'KKR IPL Journey | From Ganguly and McCullum to Gautam Gambhir',
            'description': "Kolkata Knight Riders' early IPL journey went through leadership changes and difficult seasons before the team made playoff progress under Gautam Gambhir. This chapter follows that transition through Sourav Ganguly, Brendon McCullum and the next phase of KKR's story.\n\nThe narration looks back at Ganguly's role and the franchise's struggles before moving to Gambhir's arrival in 2011. That change leads into a discussion of Kolkata reaching the playoffs and facing Mumbai Indians in the Eliminator.\n\nThe defeat to Mumbai ends that part of the campaign, while the documentary moves towards the team's next chapter. The closing passage introduces Sunil Narine's arrival in 2012, setting up another phase in Kolkata's IPL history.\n\nFor viewers following KKR's development, the focus here is on the people and turning points discussed in this section: leadership, playoff progress and the transition towards a different squad. Follow the franchise's changing direction through these chapters of the Kolkata Knight Riders journey.\n\n#KKR #KolkataKnightRiders #GautamGambhir #SouravGanguly #IPLHistory"}}
    path = FOLDER / 'prepared.json'
    manifest = json.loads(path.read_text('utf-8'))
    audit = []
    for clip in manifest['clips']:
        before = dict(clip['metadata'])
        clip['metadata'] = validate({**before, **edits[clip['name']]})
        assert 3 <= clip['metadata']['description'].count('#') <= 5
        assert not any(s in clip['metadata']['description'].lower() for s in ('do not ', 'omit ', 'upload test', 'storylens', 'unverified details'))
        audit.append({'name': clip['name'], 'before': before, 'after': clip['metadata'],
                      'reason': 'Operator reviewed source accuracy and removed instruction leakage, unsupported analysis and ambiguous statistics.'})
    manifest.update(reviewed=True, reviewed_by='operator', reviewed_at=time.time(),
                    metadata_provenance='Local 9B and 14B drafts plus explicit operator editorial corrections')
    save(FOLDER / 'editorial-review.json', audit)
    save(path, manifest)
    log('Four source-reviewed, content-only metadata entries approved; model drafts retained separately.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inspect','prepare','revise','review14b','approve','upload','verify'])
    args = parser.parse_args()
    FOLDER.mkdir(parents=True, exist_ok=True)
    {'inspect': lambda: log(json.dumps(connections())), 'prepare': prepare, 'revise': revise,
     'review14b': lambda: revise('storylens-meaning:14b'), 'approve': approve_reviewed_copy,
     'upload': upload, 'verify': verify}[args.action]()
