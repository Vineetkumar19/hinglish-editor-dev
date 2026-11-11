"""Persistent sequential downloads, YouTube sections and editor-ready assets."""
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import copy
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import uuid
import tempfile
import xml.etree.ElementTree as ET

from .user_messages import problem

QUALITIES = {'2160', '1440', '1080', '720'}
MAX_BYTES = 8 * 1024**3
MAX_BEST_YOUTUBE_BYTES = 64 * 1024**3
MAX_DURATION = 6 * 3600


def timestamp(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('Use seconds, MM:SS or HH:MM:SS for the clip times.')
    parts = str(value).strip().split(':')
    if not 1 <= len(parts) <= 3 or any(not re.fullmatch(r'\d+(?:\.\d+)?', p) for p in parts):
        raise ValueError('Use seconds, MM:SS or HH:MM:SS for the clip times.')
    if any(float(p) >= 60 for p in parts[1:]) or any('.' in p for p in parts[:-1]):
        raise ValueError('Minutes and seconds after a colon must be below 60.')
    seconds = sum(float(p) * 60**i for i, p in enumerate(reversed(parts)))
    if not math.isfinite(seconds) or seconds > MAX_DURATION:
        raise ValueError('Choose clip times within six hours.')
    return seconds


def validate_request(payload):
    if not isinstance(payload, dict): raise ValueError('Choose a video link and download settings.')
    url = payload.get('url')
    if not isinstance(url, str) or not 0 < len(url) <= 2048 or re.search(r'[\x00-\x20\x7f]', url.strip()):
        raise ValueError('Paste one public YouTube, Instagram or Pinterest video link.')
    url = url.strip()
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
            raise ValueError()
    except ValueError:
        raise ValueError('Use a normal HTTPS video link without a password or custom port.') from None
    host = (p.hostname or '').lower()
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
        valid = (p.path == '/watch' and bool(parse_qs(p.query).get('v', [''])[0])) or bool(re.fullmatch(r'/(shorts|live|embed)/[\w-]+/?', p.path))
        platform = 'youtube'
    elif host in ('youtu.be', 'www.youtu.be'):
        valid = bool(re.fullmatch(r'/[\w-]+/?', p.path)); platform = 'youtube'
    elif host in ('instagram.com', 'www.instagram.com', 'm.instagram.com'):
        valid = bool(re.fullmatch(r'/(reel|reels|p|tv)/[\w-]+/?', p.path)); platform = 'instagram'
    elif host in ('pinterest.com', 'www.pinterest.com', 'in.pinterest.com', 'uk.pinterest.com', 'pinterest.co.uk', 'www.pinterest.co.uk'):
        valid = bool(re.fullmatch(r'/pin/\d+/?', p.path)); platform = 'pinterest'
    elif host in ('pin.it', 'www.pin.it'):
        valid = bool(re.fullmatch(r'/[\w-]+/?', p.path)); platform = 'pinterest'
    elif host in ('facebook.com', 'www.facebook.com', 'm.facebook.com', 'web.facebook.com'):
        valid = ((p.path.rstrip('/') == '/watch' and bool(parse_qs(p.query).get('v', [''])[0]))
                 or bool(re.fullmatch(r'/(?:reel/\d+|[^/]+/videos/\d+|share/[rv]/[\w-]+)/?', p.path)))
        platform = 'facebook'
    elif host in ('fb.watch', 'www.fb.watch'):
        valid = bool(re.fullmatch(r'/[\w-]+/?', p.path)); platform = 'facebook'
    else:
        raise ValueError('Choose a YouTube, Instagram, Pinterest or Facebook video link.')
    if not valid:
        raise ValueError('Paste a single video, Short, Reel or video Pin link. Choose a video instead of a profile, board or playlist.')
    quality = payload.get('quality', '1080')
    mode = payload.get('mode', 'video')
    audio = payload.get('audio_format', 'wav')
    if not isinstance(quality, str) or quality not in QUALITIES | {'best'}:
        raise ValueError('Choose Highest available, 4K, 2K, 1080p or 720p.')
    if not isinstance(mode, str) or mode not in ('video', 'audio', 'both'):
        raise ValueError('Choose Video, Audio only, or Video + separate audio.')
    if not isinstance(audio, str) or audio not in ('wav', 'mp3'):
        raise ValueError('Choose WAV or MP3 for the extracted audio.')
    result = {'url': url, 'platform': platform, 'quality': quality if platform == 'youtube' else 'best', 'mode': mode, 'audio_format': audio}
    start, end = payload.get('start_time'), payload.get('end_time')
    if start not in (None, '') or end not in (None, ''):
        if platform != 'youtube': raise ValueError('Start and end times are available for YouTube only.')
        if start in (None, '') or end in (None, ''): raise ValueError('Enter both the start and end time, or leave both empty for the full video.')
        start, end = timestamp(start), timestamp(end)
        if end <= start: raise ValueError('The clip end must be after its start.')
        result['section'] = {'start': start, 'end': end}
    return result


def format_selector(quality, mode):
    if mode == 'audio': return 'bestaudio/best'
    cap = '' if quality == 'best' else f'[height<={int(quality)}]'
    return f'bestvideo{cap}+bestaudio/best{cap}'


def highest_youtube_video(request):
    return request['platform'] == 'youtube' and request['quality'] == 'best' and request['mode'] != 'audio'


def verify_video_quality(expected, actual, label):
    """Compare selected dimensions and nominal frame rate with the saved media."""
    for key in ('width', 'height'):
        if expected.get(key) and expected[key] != actual[key]:
            raise ValueError(f'{label} did not preserve the selected {key}.')
    if expected.get('fps') and abs(float(Fraction(str(expected['fps'])) - Fraction(actual['fps']))) > .1:
        raise ValueError(f'{label} did not preserve the selected frame rate.')


def probe(path):
    import av
    with av.open(str(path)) as c:
        v = c.streams.video[0] if c.streams.video else None
        a = c.streams.audio[0] if c.streams.audio else None
        duration = float(c.duration / av.time_base) if c.duration is not None else float((v or a).duration * (v or a).time_base)
        if not math.isfinite(duration) or duration <= 0: raise ValueError('This download has no usable duration. Try another video link.')
        return {'duration': duration, 'fps': str(v.average_rate or 30) if v else '30', 'width': v.width if v else 0,
                'height': v.height if v else 0, 'channels': a.channels if a else 0, 'sample_rate': a.sample_rate if a else 48000,
                'video_codec': v.codec_context.name if v else '', 'audio_codec': a.codec_context.name if a else ''}


def export_timeline(path, info, kind):
    """FCP7 XML: an audio export has audio clips only, with no dummy video."""
    from hinglish_cut.xml_export import add, rate, premiere_pathurl, video_format_dimensions
    fps = Fraction(info['fps'])
    supported = [Fraction(n) for n in (24, 25, 30, 50, 60, 120)] + [Fraction(n*1000, 1001) for n in (24, 30, 60, 120)]
    fps = min(supported, key=lambda f: abs(float(f-fps)))
    frames = max(1, round(info['duration'] * float(fps)))
    root = ET.Element('xmeml', version='5'); seq = add(root, 'sequence', id='download-sequence')
    add(seq, 'name', path.parent.parent.name + ' ' + kind); add(seq, 'duration', frames); rate(seq, str(fps))
    med = add(seq, 'media'); video = add(med, 'video')
    video_format_dimensions(add(add(video, 'format'), 'samplecharacteristics'), info['width'] or 1920, info['height'] or 1080, str(fps))
    if kind == 'video': vt = add(video, 'track')
    audio = add(med, 'audio'); add(audio, 'numOutputChannels', info['channels'])
    af = add(add(audio, 'format'), 'samplecharacteristics'); add(af, 'depth', 16); add(af, 'samplerate', info['sample_rate'])
    lanes = ([('video', vt, 1)] if kind == 'video' else []) + [('audio', add(audio, 'track'), n+1) for n in range(info['channels'])]
    for index, (media_kind, track, channel) in enumerate(lanes):
        ci = add(track, 'clipitem', id=f'download-{media_kind}-{channel}')
        add(ci, 'name', path.name); add(ci, 'enabled', 'TRUE'); add(ci, 'duration', frames); rate(ci, str(fps))
        for key, value in [('start', 0), ('end', frames), ('in', 0), ('out', frames)]: add(ci, key, value)
        file = add(ci, 'file', id='download-file')
        if index == 0:
            add(file, 'name', path.name); add(file, 'pathurl', premiere_pathurl(path)); add(file, 'duration', frames); rate(file, str(fps))
            fm = add(file, 'media')
            if kind == 'video': video_format_dimensions(add(add(fm, 'video'), 'samplecharacteristics'), info['width'], info['height'], str(fps))
            if info['channels']:
                fa = add(fm, 'audio'); sc = add(fa, 'samplecharacteristics'); add(sc, 'depth', 16); add(sc, 'samplerate', info['sample_rate']); add(fa, 'channelcount', info['channels'])
        if media_kind == 'audio':
            source = add(ci, 'sourcetrack'); add(source, 'mediatype', 'audio'); add(source, 'trackindex', channel)
    ET.indent(root, space='  ')
    dest = path.parent / 'DOWNLOADED_SEQUENCE.xml'; ET.ElementTree(root).write(dest, encoding='utf-8', xml_declaration=True)
    return dest


class DownloadService:
    def __init__(self, root):
        self.root = Path(root).resolve(); self.base = self.root / 'output/downloads'
        self.lock = threading.RLock(); self.jobs = {}; self.events = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='storylens-download')
        self.futures = {}; self.closed = False

    def close(self):
        self.closed = True
        for event in self.events.values(): event.set()
        self.pool.shutdown(wait=True, cancel_futures=True)

    def _folder(self, id):
        if not isinstance(id, str) or not re.fullmatch('[a-f0-9]{32}', id): raise ValueError('Choose a saved download from the list.')
        path = (self.base / id).resolve()
        if not path.is_relative_to(self.base.resolve()): raise ValueError('Choose a saved download from the list.')
        return path

    def _save(self, id, **values):
        with self.lock:
            self.jobs[id].update(values)
            path = self._folder(id) / 'job.json'
            temp = path.with_suffix('.tmp'); temp.write_text(json.dumps(self.jobs[id], ensure_ascii=False, indent=2), encoding='utf-8'); os.replace(temp, path)

    def snapshot(self, id):
        folder = self._folder(id)
        with self.lock:
            if id not in self.jobs:
                if not (folder / 'job.json').is_file(): raise ValueError('This saved download is unavailable. Start a new download.')
                job = json.loads((folder / 'job.json').read_text(encoding='utf-8'))
                if job['status'] in ('queued', 'running'):
                    job.update(status='interrupted', stage='Paused after app restart', error=problem(ValueError('The app stopped before this download finished. Resume this queue item; saved files are kept.'), feature='Downloader'))
                self.jobs[id] = job
            return copy.deepcopy(self.jobs[id])

    def history(self):
        jobs = []
        for path in self.base.glob('*/job.json'):
            try: jobs.append(self.snapshot(path.parent.name))
            except (ValueError, OSError): continue
        active = sorted((j for j in jobs if j['status'] in ('queued','running','interrupted')), key=lambda j:j['created'])
        finished = sorted((j for j in jobs if j['status'] not in ('queued','running','interrupted')), key=lambda j:j['created'], reverse=True)[:100]
        return sorted(active + finished, key=lambda j:j.get('queued_at',j['created']))

    def queue(self):
        # The owner's hidden legacy history stays hidden; show the new queue only.
        return [j for j in self.history() if j.get('queue_version') == 1 or j['status'] in ('queued','running')]

    def settings(self, payload=None):
        path = self.base / 'settings.json'
        with self.lock:
            data = json.loads(path.read_text('utf-8')) if path.is_file() else {}
            if payload is not None:
                value = payload.get('destination')
                if not isinstance(value, str) or not value.strip() or '\x00' in value:
                    raise ValueError('Choose a folder for your downloads.')
                folder = Path(value).expanduser()
                if not folder.is_absolute(): raise ValueError('Use a full folder path for your downloads.')
                folder = folder.resolve()
                if not folder.is_dir(): raise ValueError('This download folder is unavailable. Choose an existing folder.')
                # Check write access now, before a long transfer is queued.
                with tempfile.TemporaryFile(dir=folder): pass
                data = {'destination': str(folder)}
                self.base.mkdir(parents=True, exist_ok=True)
                temp = path.with_suffix('.tmp'); temp.write_text(json.dumps(data), encoding='utf-8'); os.replace(temp,path)
            return data

    def start(self, payload):
        request = validate_request(payload)
        with self.lock:
            if self.closed: raise ValueError('The download queue is closing. Reopen Downloader to continue.')
            # Restore saved identities before deciding whether this HTTP retry is new.
            self.history()
            destination = payload.get('destination') or self.settings().get('destination')
            if destination: request['destination'] = self.settings({'destination': destination})['destination']
            submission = payload.get('submission_id')
            if submission is not None and (not isinstance(submission,str) or not re.fullmatch(r'[\w-]{1,100}',submission)):
                raise ValueError('Refresh Downloader and submit the link again.')
            if submission:
                existing = next((j for j in self.jobs.values() if j.get('submission_id') == submission), None)
                if existing:
                    if existing['request'] != request: raise ValueError('This download submission already belongs to another link or setting.')
                    return self.snapshot(existing['id'])
            if sum(j['status'] in ('queued','running') for j in self.jobs.values()) >= 200:
                raise ValueError('The queue already has 200 pending downloads. Wait for a few to finish before adding more.')
            id = uuid.uuid4().hex; self._folder(id).mkdir(parents=True)
            self.events[id] = threading.Event()
            self.jobs[id] = {'id':id, 'status':'queued', 'stage':'Waiting in queue', 'progress':0, 'request':request, 'created':time.time(), 'queued_at':time.time(), 'queue_version':1, 'submission_id':submission}
            self._save(id); self.futures[id] = self.pool.submit(self._execute, id, self.events[id])
            return self.snapshot(id)

    def enqueue(self, payload):
        requests = payload.get('requests')
        if not isinstance(requests,list) or not 1 <= len(requests) <= 200:
            raise ValueError('Add between 1 and 200 video links to the queue.')
        with self.lock:
            self.history()
            known={j.get('submission_id'):j for j in self.jobs.values() if j.get('submission_id')}
            pending=sum(j['status'] in ('queued','running') for j in self.jobs.values())
            submissions=set()
            for request in requests:
                validated=validate_request(request)
                destination=request.get('destination') or self.settings().get('destination')
                if destination: validated['destination']=self.settings({'destination':destination})['destination']
                submission=request.get('submission_id')
                if submission is not None and (not isinstance(submission,str) or not re.fullmatch(r'[\w-]{1,100}',submission)):
                    raise ValueError('Refresh Downloader and submit the links again.')
                if submission and submission in submissions: raise ValueError('Each queue entry needs its own submission identity. Refresh Downloader and try again.')
                if submission: submissions.add(submission)
                if submission in known and known[submission]['request']!=validated:
                    raise ValueError('This download submission already belongs to another link or setting.')
            if pending+sum(r.get('submission_id') not in known for r in requests)>200:
                raise ValueError('The queue can hold 200 pending downloads. Wait for a few to finish before adding more.')
            return {'jobs':[self.start(request) for request in requests]}

    def _execute(self, id, event):
        with self.lock:
            if event.is_set() or self.events[id] is not event or self.jobs[id]['status'] != 'queued': return
            self._save(id,status='running',stage='Checking the video link')
        self._run(id)

    def retry(self, id):
        with self.lock:
            job = self.snapshot(id)
            if job['status'] in ('queued','running','complete'): return job
            if self.closed: raise ValueError('The download queue is closing. Reopen Downloader to continue.')
            if sum(j['status'] in ('queued','running') for j in self.jobs.values()) >= 200:
                raise ValueError('The queue already has 200 pending downloads. Wait for a few to finish before retrying.')
            self.events[id] = threading.Event()
            self._save(id,status='queued',stage='Waiting in queue',error=None,progress=0,queued_at=time.time(),queue_version=1)
            self.futures[id] = self.pool.submit(self._execute,id,self.events[id])
            return self.snapshot(id)

    def cancel(self, id):
        with self.lock:
            job = self.snapshot(id)
            if job['status'] in ('queued', 'running') and id in self.events:
                self.events[id].set()
                if job['status'] == 'queued':
                    if id in self.futures: self.futures[id].cancel()
                    self._save(id,status='cancelled',stage='Download cancelled')
                else: self._save(id,stage='Cancelling download')
            elif job['status'] == 'interrupted': self._save(id,status='cancelled',stage='Download cancelled')
            return self.snapshot(id)

    def save_asset(self, id, source, title, kind, cancel):
        """Copy once to the chosen folder, never replacing an existing user file."""
        job = self.snapshot(id); destination = job['request'].get('destination')
        if not destination: return source
        folder = Path(destination)
        if not folder.is_dir(): raise ValueError('Your download folder is unavailable. Reconnect the drive, then resume this item.')
        saved = job.get('saved_files', {}).get(kind)
        if saved and Path(saved).is_file() and Path(saved).stat().st_size == source.stat().st_size: return Path(saved)
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', title).strip(' .')[:100] or 'Video'
        name = f'{stem}--{id[:8]}-{kind}{source.suffix}'
        target = folder / name
        temp = folder / ('.storylens-' + uuid.uuid4().hex + '.part')
        try:
            with source.open('rb') as src, temp.open('xb') as dst:
                while chunk := src.read(1024*1024):
                    if cancel.is_set(): raise ValueError('Download cancelled. Saved files are kept.')
                    dst.write(chunk)
            # Exclusive hardlink is atomic and refuses to replace an existing file.
            for number in range(1000):
                candidate = target if not number else folder / f'{target.stem}-{number}{target.suffix}'
                try:
                    os.link(temp,candidate); target=candidate; break
                except FileExistsError: continue
                except OSError:
                    # Drives without hardlinks still use exclusive creation.
                    try:
                        with candidate.open('xb') as dst:
                            try:
                                with temp.open('rb') as src: shutil.copyfileobj(src,dst,1024*1024)
                            except BaseException:
                                dst.close();candidate.unlink(missing_ok=True);raise
                        target=candidate; break
                    except FileExistsError: continue
            else: raise ValueError('Choose another download folder; too many files share this name.')
            records = dict(job.get('saved_files',{})); records[kind] = str(target)
            self._save(id,saved_files=records)
            return target
        finally:
            temp.unlink(missing_ok=True)

    def media(self, id, kind):
        if kind not in ('video', 'audio'): raise ValueError('Choose the downloaded video or audio.')
        job = self.snapshot(id)
        asset = (job.get('result') or {}).get('assets', {}).get(kind)
        if not asset: raise ValueError('This file is not ready. Finish the download first.')
        path = Path(asset['path']).resolve()
        if not path.is_relative_to(self._folder(id)) or not path.is_file(): raise ValueError('The downloaded file has moved. Start a new download or use your saved copy.')
        return path

    def transfer(self, request, folder, progress, cancel):
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadCancelled
        import imageio_ffmpeg
        def guard(url):
            parsed = urlsplit(url)
            if parsed.scheme not in ('http','https') or not parsed.hostname: raise ValueError('This video points to an unsupported media source. Choose another link.')
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme=='https' else 80), type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ValueError('This video points to a private network address. Choose a public video link.')
        class PublicYoutubeDL(YoutubeDL):
            def urlopen(self, req):
                if cancel.is_set(): raise DownloadCancelled('Download cancelled')
                guard(req if isinstance(req,str) else req.url)
                return super().urlopen(req)
        highest = highest_youtube_video(request)
        max_bytes = MAX_BEST_YOUTUBE_BYTES if highest and not request.get('section') else MAX_BYTES
        hook_lock = threading.Lock()
        last_update = -math.inf
        def hook(d):
            nonlocal last_update
            if cancel.is_set(): raise DownloadCancelled('Download cancelled')
            count=d.get('downloaded_bytes',0)
            if count > max_bytes:
                raise ValueError(f'This download exceeded the {max_bytes // 1024**3} GiB limit. Choose a shorter video.')
            total=d.get('total_bytes') or d.get('total_bytes_estimate')
            # Hooks run for every network buffer and on multiple fragment threads.
            # Persist at most twice per second, rather than writing job JSON for
            # every packet. Cancellation and size checks above remain immediate.
            with hook_lock:
                now = time.monotonic()
                if d.get('status') == 'finished' or now - last_update >= .5:
                    progress('Downloading media', min(85, int(85*count/total)) if total else None)
                    last_update = now
        def match(info, *, incomplete=False):
            if info.get('is_live'): return 'Choose a finished video instead of a live stream.'
            if (info.get('duration') or 0) > MAX_DURATION: return 'Choose a video of six hours or less.'
        class Logger:
            def debug(self, message): pass
            def warning(self, message): pass
            def error(self, message): pass
        opts = {'format':'bv*+ba/b' if highest else format_selector(request['quality'],request['mode']), 'outtmpl':str(folder/'source.%(ext)s'),
                'noplaylist':True, 'playlistend':1, 'max_filesize':max_bytes, 'match_filter':match,
                'socket_timeout':20, 'retries':2, 'fragment_retries':2, 'concurrent_fragment_downloads':6,
                'buffersize':64*1024, 'continuedl':True, 'skip_unavailable_fragments':False,
                'ffmpeg_location':imageio_ffmpeg.get_ffmpeg_exe(), 'merge_output_format':'mp4/mkv',
                'progress_hooks':[hook], 'logger':Logger(), 'quiet':True, 'no_warnings':True,
                'windowsfilenames':True, 'overwrites':False, 'cachedir':False, 'check_formats':'selected'}
        if highest:
            opts.update(format_sort=['res', 'fps', 'width'], format_sort_force=True)
        node=shutil.which('node') or ('C:/Program Files/nodejs/node.exe' if Path('C:/Program Files/nodejs/node.exe').is_file() else None)
        if node: opts['js_runtimes']={'node':{'path':node}}
        with PublicYoutubeDL(opts) as ydl:
            info = ydl.extract_info(request['url'], download=False)
            if not info or info.get('_type') in ('playlist','multi_video') or info.get('entries'):
                raise ValueError('Choose a single video instead of a multi-video post or playlist.')
            if info.get('is_live') or (info.get('duration') or 0)>MAX_DURATION:
                raise ValueError('Choose a finished video of six hours or less.')
            if highest and info.get('live_status') == 'post_live':
                raise ValueError('YouTube is still processing the replay. Retry when the highest quality is available.')
            title = {'title':str(info.get('title') or 'Downloaded media')[:240]}
            if highest:
                formats = info.get('requested_formats') or [info]
                selected = next((f for f in formats if f.get('vcodec') not in (None, 'none')), info)
                title['selected_video'] = {key:selected.get(key) for key in ('format_id', 'width', 'height', 'fps')}
                if not request.get('section'):
                    estimate = sum(f.get('filesize') or f.get('filesize_approx') or 0 for f in formats)
                    if estimate > max_bytes:
                        raise ValueError('The highest quality exceeds the 64 GiB download limit.')
                    if estimate and 2 * estimate > shutil.disk_usage(folder).free:
                        raise ValueError('Free more disk space for the highest-quality replay and its merged file.')
            progress('Downloading selected quality',2)
            if request.get('section'):
                path = self._section_transfer(request,info,folder,progress,cancel,guard)
                return path, title
            ydl.process_ie_result(info, download=True)
        files=[p for p in folder.glob('source.*') if p.suffix.lower() in ('.mp4','.mkv','.webm','.mov','.m4a','.mp3','.opus','.ogg','.wav')]
        if not files: raise ValueError('No downloadable media was returned. Choose another public video link.')
        return max(files,key=lambda p:p.stat().st_size), title

    def _section_transfer(self, request, info, folder, progress, cancel, guard):
        """Seek the remote source before decoding; never fetch the full source first."""
        from hinglish_cut.compute_policy import ffmpeg_h264, heavy_device
        start, end = request['section']['start'], request['section']['end']
        duration = info.get('duration')
        if not duration or end > float(duration) + .05:
            raise ValueError('The requested clip is outside this video. Choose an end time within its duration.')
        formats = info.get('requested_formats') or [info]
        video = next((i for i,f in enumerate(formats) if f.get('vcodec','none') != 'none'), None)
        audio = next((i for i,f in enumerate(formats) if f.get('acodec','none') != 'none'), None)
        if request['mode'] != 'audio' and video is None: raise ValueError('This link has no downloadable video track.')
        if request['mode'] == 'audio' and audio is None: raise ValueError('This video has no audio track.')
        args=[]
        for fmt in formats:
            url=fmt.get('url',''); guard(url)
            args+=['-rw_timeout','20000000','-ss',str(start)]
            headers=fmt.get('http_headers') or info.get('http_headers') or {}
            headers={k:str(v) for k,v in headers.items() if re.fullmatch(r'[A-Za-z0-9-]+',k) and not re.search(r'[\r\n\x00]',str(v))}
            if headers: args+=['-headers',''.join(f'{k}: {v}\r\n' for k,v in headers.items())]
            args+=['-i',url]
        args+=['-t',str(end-start)]
        if request['mode'] != 'audio':
            args+=['-map',f'{video}:v:0',*ffmpeg_h264(heavy_device(self.root),18),'-pix_fmt','yuv420p']
        else: args+=['-vn']
        if audio is not None: args+=['-map',f'{audio}:a:0','-c:a','aac','-b:a','256k']
        target=folder/('source-section.m4a' if request['mode']=='audio' else 'source-section.mp4')
        args+=['-fs',str(MAX_BYTES),'-movflags','+faststart',str(target)]
        def section_progress(fraction):
            progress('Downloading selected time range', min(85, 2 + int(83 * fraction)))

        self._ffmpeg(args, cancel, progress=section_progress, duration=end-start)
        if target.stat().st_size >= MAX_BYTES: raise ValueError('This clip reached the 8 GB limit. Choose a shorter time range.')
        return target

    def _ffmpeg(self,args,cancel,**kwargs):
        from contextlib import nullcontext
        from hinglish_cut.gpu_lock import gpu_lock
        with gpu_lock(self.root) if 'h264_nvenc' in args else nullcontext():
            return self._ffmpeg_unlocked(args,cancel,**kwargs)

    def _ffmpeg_unlocked(self, args, cancel, progress=None, duration=None):
        import imageio_ffmpeg
        track_progress = progress is not None and duration is not None and duration > 0
        # On Windows communicate() does not expose partial pipe output on timeout.
        # Drain progress independently while the worker checks cancellation.
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(
                [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                 *(['-progress', 'pipe:1', '-nostats'] if track_progress else []), *args],
                stdout=subprocess.PIPE if track_progress else subprocess.DEVNULL,
                stderr=errors, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            media_time = 0

            def read_progress():
                nonlocal media_time
                with process.stdout as stream:
                    for line in stream:
                        key, _, value = line.strip().partition(b'=')
                        if key == b'out_time_us' and value.isdigit():
                            media_time = max(media_time, int(value))

            reader = None
            last_report = 0
            try:
                if track_progress:
                    reader = threading.Thread(target=read_progress)
                    reader.start()
                while True:
                    try:
                        process.wait(timeout=.4)
                        break
                    except subprocess.TimeoutExpired:
                        if cancel.is_set():
                            process.terminate()
                            raise ValueError('Download cancelled. Saved files are kept.')
                        current_time = media_time
                        if current_time > last_report:
                            progress(min(1, current_time / 1e6 / duration))
                            last_report = current_time
                if process.returncode:
                    size = errors.seek(0, os.SEEK_END)
                    errors.seek(max(0, size - 5000))
                    raise RuntimeError(errors.read().decode('utf-8', errors='replace'))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if reader is not None:
                    reader.join()

    def _run(self, id):
        from hinglish_cut.compute_policy import ffmpeg_h264
        from hinglish_cut.compute_policy import heavy_device
        event=self.events[id]; request=self.jobs[id]['request']; folder=self._folder(id)
        started = time.monotonic(); timings = {}
        def progress(stage, value=None):
            if event.is_set(): raise ValueError('Download cancelled. Saved files are kept.')
            self._save(id,status='running',stage=stage,stage_progress=None,
                       **({'progress':max(value,self.jobs[id].get('progress',0))} if value is not None else {}))

        def prepare_progress(fraction):
            percent = min(99, int(100 * fraction))
            if percent != self.jobs[id].get('stage_progress'):
                self._save(id, stage_progress=percent)

        assets=copy.deepcopy((self.jobs[id].get('result') or {}).get('assets',{}))
        try:
            progress('Checking the video link',0)
            saved_source=Path(self.jobs[id].get('source') or folder/'not-ready').resolve()
            if saved_source.is_relative_to(folder) and saved_source.is_file():
                source=saved_source
                title={'title':self.jobs[id].get('title') or 'Downloaded media',
                       'selected_video':self.jobs[id].get('selected_video')}
            else:
                if self.jobs[id].get('source'):
                    self._save(id, source=None)
                source, title=self.transfer(request,folder,progress,event)
            original=probe(source)
            selected=title.get('selected_video')
            if selected:
                verify_video_quality(selected, original, 'The downloaded replay')
                if source.stat().st_size > MAX_BEST_YOUTUBE_BYTES:
                    raise ValueError('The merged replay exceeds the 64 GiB download limit.')
            timings['download_seconds'] = round(time.monotonic() - started, 3)
            self._save(id,source=str(source),title=title['title'],timings=timings,
                       stage='Preparing downloaded media',
                       **({'selected_video':selected} if selected else {}))
            if request['mode']!='audio' and not original['width']: raise ValueError('This link has no video. Choose Audio only or use another video link.')
            if original['duration']>MAX_DURATION: raise ValueError('Choose a video of six hours or less. Saved files are kept.')
            self._save(id,title=title['title'])
            for kind in (('video','audio') if request['mode']=='both' else (request['mode'],)):
                existing=assets.get(kind)
                if existing and Path(existing['path']).resolve().is_relative_to(folder) and Path(existing['path']).is_file():
                    progress('Saving to your folder')
                    saved=self.save_asset(id,Path(existing['path']),title['title'],kind,event)
                    assets[kind]['saved_path']=str(saved)
                    continue
                target=folder/kind; target.mkdir(exist_ok=True)
                preparing = time.monotonic()
                ready_mp4 = (kind == 'video' and source.suffix.lower() == '.mp4'
                             and original['video_codec'] == 'h264'
                             and original['audio_codec'] in ('aac', ''))
                if kind=='video':
                    progress('Preparing video for your editor',87)
                    dest=target/'downloaded-video.mp4'
                    args=['-i',str(source),'-map','0:v:0','-map','0:a:0?']
                    args+=['-c:v','copy'] if original['video_codec']=='h264' else [*ffmpeg_h264(heavy_device(self.root),16),'-pix_fmt','yuv420p','-threads','2']
                    args+=['-c:a','copy'] if original['audio_codec']=='aac' else ['-c:a','aac','-b:a','320k']
                    args+=['-movflags','+faststart',str(dest)]
                else:
                    if not original['channels']: raise ValueError('This video has no audio track. Use its saved video or choose another link.')
                    progress('Extracting separate audio',94)
                    dest=target/('extracted-audio.'+request['audio_format'])
                    args=['-i',str(source),'-map','0:a:0','-vn','-ar','48000']
                    args+=['-c:a','pcm_s24le'] if request['audio_format']=='wav' else ['-c:a','libmp3lame','-b:a','320k']
                    args+=[str(dest)]
                if ready_mp4:
                    # The downloader already produced editor-ready MP4. Avoid
                    # reading/writing the entire 4K video through FFmpeg again.
                    dest.unlink(missing_ok=True)
                    try:
                        os.link(source, dest)
                    except OSError:
                        with source.open('rb') as reader, dest.open('xb') as writer:
                            while data := reader.read(1024 * 1024):
                                if event.is_set(): raise ValueError('Download cancelled. Saved files are kept.')
                                writer.write(data)
                else:
                    self._ffmpeg(args, event, progress=prepare_progress, duration=original['duration'])
                info=probe(dest)
                if kind == 'video' and highest_youtube_video(request):
                    verify_video_quality(original, info, 'The editor-ready replay')
                xml=export_timeline(dest,info,kind)
                timings[kind + '_prepare_seconds'] = round(time.monotonic() - preparing, 3)
                assets[kind]={'path':str(dest),'folder':str(target),'xml_files':[str(xml)],'kind':kind,**info}
                self._save(id,result={'assets':assets,'title':title['title']})
                progress('Saving to your folder',90 if request['mode']=='both' and kind=='video' else 98)
                saving = time.monotonic()
                saved=self.save_asset(id,dest,title['title'],kind,event)
                timings[kind + '_save_seconds'] = round(time.monotonic() - saving, 3)
                assets[kind]['saved_path']=str(saved)
                self._save(id,result={'assets':assets,'title':title['title']})
            progress('Finalizing saved files',99)
            notice=''
            if request['quality']!='best' and assets.get('video') and assets['video']['height']<int(request['quality']):
                notice=f"Downloaded {assets['video']['height']}p: this video did not provide the requested {request['quality']}p format."
            elif highest_youtube_video(request) and assets.get('video'):
                asset=assets['video']
                notice=f"Highest available video saved at {asset['width']} × {asset['height']} and {float(Fraction(asset['fps'])):g} fps."
            timings['total_seconds'] = round(time.monotonic() - started, 3)
            self._save(id,status='complete',stage='Complete',progress=100,finished=time.time(),timings=timings,
                       result={'assets':assets,'title':title['title'],'notice':notice})
        except Exception as error:
            self._save(id,status='cancelled' if event.is_set() else 'failed',stage='Download cancelled' if event.is_set() else 'Download stopped',error=None if event.is_set() else problem(error,feature='Downloader'))


_SERVICES={}; _SERVICES_LOCK=threading.Lock()
def service(root):
    key=str(Path(root).resolve())
    with _SERVICES_LOCK:
        if key not in _SERVICES: _SERVICES[key]=DownloadService(root)
        return _SERVICES[key]
