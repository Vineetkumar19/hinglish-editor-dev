"""Read-only samples; hypotheses and unavailable sensors remain explicit."""
import json
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone

import httpx
import psutil
from core import local_store as store
from core.config import settings
from core.tasks import check_cancelled


def _gpu():
    binary = shutil.which('nvidia-smi')
    if not binary:
        return {'available': False, 'reason': 'NVIDIA telemetry tool unavailable.'}
    try:
        result = subprocess.run([binary, '--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu,utilization.encoder,utilization.decoder,clocks_event_reasons.hw_thermal_slowdown,clocks_event_reasons.sw_thermal_slowdown',
            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True)
        processes=subprocess.run([binary,'--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader,nounits'],
            capture_output=True,text=True,timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return {'available': True, 'fields': ['name','vram_total_MiB','vram_used_MiB','gpu_percent','temperature_C',
                'encoder_percent','decoder_percent','hardware_thermal_slowdown','software_thermal_slowdown'],
                'rows': [line.split(', ') for line in result.stdout.strip().splitlines()],
                'compute_process_rows':[line.split(', ') for line in processes.stdout.strip().splitlines()] if processes.returncode==0 else [],
                'note':'N/A means the driver did not expose that measurement; utilization alone is not throttling evidence.'}
    except (OSError, subprocess.SubprocessError):
        return {'available': False, 'reason': 'Telemetry query failed.'}


def _models():
    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            response = client.get(settings.ollama_host + '/api/ps')
            response.raise_for_status()
            return {'available': True, 'models': response.json().get('models', [])}
    except (httpx.HTTPError, ValueError):
        return {'available': False, 'models': [], 'reason': 'Local runtime unavailable.'}


def _power_mode():
    binary=shutil.which('powercfg')
    if not binary:
        return {'available':False,'reason':'Windows power-plan query unavailable.'}
    try:
        result=subprocess.run([binary,'/getactivescheme'],capture_output=True,text=True,timeout=4,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
        return {'available':True,'active_scheme':result.stdout.strip()[:400],
                'note':'Windows power scheme only; vendor performance/fan modes were not changed or inferred.'}
    except (OSError,subprocess.SubprocessError):
        return {'available':False,'reason':'Power-plan query failed.'}


def _events():
    try:
        import win32evtlog
        import xml.etree.ElementTree as ET
        events=[]
        for channel in ('Application','System'):
            query=win32evtlog.EvtQuery(channel,win32evtlog.EvtQueryReverseDirection,
                '*[System[(Level=1 or Level=2) and TimeCreated[timediff(@SystemTime) <= 86400000]]]')
            try:
                handles=win32evtlog.EvtNext(query,20)
                for event in handles:
                    try:
                        xml=ET.fromstring(win32evtlog.EvtRender(event,win32evtlog.EvtRenderEventXml))
                        ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
                        system=xml.find('e:System',ns)
                        events.append({'channel':channel,'provider':system.find('e:Provider',ns).get('Name'),
                            'event_id':system.findtext('e:EventID',namespaces=ns),
                            'at':system.find('e:TimeCreated',ns).get('SystemTime')})
                    finally:
                        event.Close()
            finally:
                query.Close()
        return {'available':True,'events':events,'scope':'Last 24 hours, critical/error, maximum 20 per channel; message text excluded.'}
    except Exception as exc:
        return {'available':False,'reason':type(exc).__name__}


def findings(samples):
    result = []
    pressure = [s for s in samples if s['memory']['available'] / s['memory']['total'] < .1]
    if len(pressure) >= max(1, len(samples) * .7):
        result.append({'rank': 1, 'finding': 'Sustained low available memory', 'confidence': 'measured',
            'evidence': f'{len(pressure)}/{len(samples)} samples below 10% available RAM.',
            'hypothesis': 'Memory pressure may contribute to lag; utilization alone does not establish its cause.',
            'proposed_action': 'Review the listed applications and close only work you have saved.'})
    high_cpu = [s for s in samples if sum(s['cpu_per_core']) / max(1, len(s['cpu_per_core'])) > 85]
    if len(high_cpu) >= max(1, len(samples) * .7):
        result.append({'rank': len(result)+1, 'finding': 'Sustained CPU utilization above 85%', 'confidence': 'measured',
            'evidence': f'{len(high_cpu)}/{len(samples)} samples.',
            'hypothesis': 'An active workload may explain reduced responsiveness; this is not proof of thermal throttling.',
            'proposed_action': 'Inspect the process samples before pausing a workload.'})
    commit_samples=[s.get('native_counters',{}).get('values',{}) for s in samples]
    commit_samples=[s for s in commit_samples if s.get('commit_limit_bytes',0)>0 and 'committed_bytes' in s]
    commit_pressure=[s for s in commit_samples if s['committed_bytes']/s['commit_limit_bytes']>.9]
    if commit_samples and len(commit_pressure)>=max(1,len(commit_samples)*.7):
        result.append({'rank':len(result)+1,'finding':'Sustained high committed-memory usage','confidence':'measured',
            'evidence':f'{len(commit_pressure)}/{len(commit_samples)} samples above 90% of the Windows commit limit.',
            'hypothesis':'Little commit headroom can constrain new allocations. This is separate from cached RAM and does not alone prove paging caused the slowdown.',
            'proposed_action':'Inspect application memory and save work before choosing anything to close.'})
    if not result:
        result.append({'rank': 1, 'finding': 'No sustained RAM/CPU threshold breach in this window', 'confidence': 'limited',
            'evidence': f'{len(samples)} samples. Disk latency, sensors and intermittent symptoms need separate evidence.',
            'hypothesis': 'This window may not contain the reported slowdown.', 'proposed_action': 'Repeat while the symptom occurs.'})
    disks=[s.get('native_counters',{}).get('values',{}) for s in samples]
    disk_samples=[s for s in disks if 'disk_active_percent' in s]
    busy=[s for s in disk_samples if s['disk_active_percent']>90]
    if disk_samples and len(busy)>=max(1,len(disk_samples)*.7):
        result.append({'rank':len(result)+1,'finding':'Sustained high disk activity','confidence':'measured',
            'evidence':f'{len(busy)}/{len(disk_samples)} aggregate disk samples above 90% active time.',
            'hypothesis':'Disk work may contribute to delays. Active time is separate from free space; inspect transfer latency and queue length.',
            'proposed_action':'Wait for known file transfers or exports, then repeat the measurement; no workload is stopped automatically.'})
    return result


def sample_system(seconds=30):
    from core.windows_counters import WindowsCounters
    with WindowsCounters() as native:
        return _sample_system(seconds,native)


def _sample_system(seconds,native):
    if not 30 <= seconds <= 60:
        raise ValueError('Use a 30–60 second observation window.')
    samples, started = [], time.time()
    psutil.cpu_percent(percpu=True)
    processes = {p.pid: p for p in psutil.process_iter()}
    for p in processes.values():
        try:
            p.cpu_percent()
        except psutil.Error:
            pass
    initial_disk = psutil.disk_io_counters()
    while time.time() - started < seconds:
        check_cancelled()
        time.sleep(max(0,min(1, seconds - (time.time() - started))))
        check_cancelled()
        memory = psutil.virtual_memory()
        top = []
        for p in psutil.process_iter(['pid', 'name', 'memory_info', 'create_time']):
            try:
                tracked = processes.get(p.pid)
                if not tracked or tracked.create_time() != p.info['create_time']:
                    tracked = p
                    processes[p.pid] = p
                top.append({'pid': p.pid, 'name': p.info['name'], 'created': p.info['create_time'],
                            'rss': p.info['memory_info'].rss, 'cpu_percent': tracked.cpu_percent()})
            except (psutil.Error, TypeError):
                continue
        disk = psutil.disk_io_counters()
        samples.append({'at': time.time(), 'memory': {'total': memory.total, 'available': memory.available,
            'used': memory.used, 'percent': memory.percent}, 'swap': psutil.swap_memory()._asdict(),
            'cpu_per_core': psutil.cpu_percent(percpu=True),
            'processes': sorted(top, key=lambda p:p['rss'], reverse=True)[:12],
            'disk': disk._asdict() if disk else None, 'native_counters':native.sample()})
    disks = []
    for disk in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(disk.mountpoint)
            disks.append({'mountpoint': disk.mountpoint, **usage._asdict()})
        except OSError:
            pass
    final_disk=psutil.disk_io_counters()
    disk_observation={'request_latency':'unknown','active_time_percent':'unknown'}
    if initial_disk and final_disk:
        for operation in ('read','write'):
            count=getattr(final_disk,operation+'_count')-getattr(initial_disk,operation+'_count')
            duration=getattr(final_disk,operation+'_time')-getattr(initial_disk,operation+'_time')
            disk_observation[operation+'_count']=count
            disk_observation[operation+'_mean_time_ms']=duration/count if count>0 else None
        disk_observation['note']='OS aggregate I/O time per completed operation; not queue latency or active-time percentage.'
    disk_samples=[s['native_counters']['values'] for s in samples if 'disk_active_percent' in s['native_counters']['values']]
    if disk_samples:
        disk_observation.update(active_time_percent_mean=sum(s['disk_active_percent'] for s in disk_samples)/len(disk_samples),
            active_time_percent='measured in per-sample native counters',
            transfer_latency='Windows Avg. Disk sec/Transfer, converted to milliseconds per sample',
            scope='PhysicalDisk(_Total), aggregated across all drives; not per-file attribution')
    conclusions=findings(samples)
    for disk in disks:
        if disk['percent']>95:
            conclusions.insert(0,{'rank':1,'finding':f"Low free space on {disk['mountpoint']}",
                'confidence':'measured','evidence':f"{disk['free']/1024**3:.2f} GiB free; {disk['percent']}% used.",
                'hypothesis':'Low capacity can constrain temporary files and paging. It is separate from disk active time.',
                'proposed_action':'Review storage usage and choose files to archive; no files are deleted automatically.'})
    for rank,conclusion in enumerate(conclusions,1):conclusion['rank']=rank
    power=_power_mode()
    unknown=['CPU thermal state','Causal correlation with event logs']
    if not disk_samples:unknown.append('Disk active-time percentage and transfer latency')
    if not power['available']:unknown.append('Windows power scheme')
    return store.put('diagnostic', {'device_id': platform.node(), 'started_at': started, 'finished_at': time.time(),
        'samples': samples, 'findings': conclusions, 'disk_capacity': disks, 'gpu': _gpu(),
        'model_runtime': _models(), 'events':_events(), 'disk_observation':disk_observation,'power_mode':power,
        'initial_disk': initial_disk._asdict() if initial_disk else None,
        'unknown': unknown, 'actions_executed': []})


def compare_reports(before_id, after_id):
    before, after = store.get('diagnostic', before_id), store.get('diagnostic', after_id)
    if before['device_id'] != after['device_id']:
        raise ValueError('Compare measurements from the same device.')
    def means(report):
        samples = report['samples']
        return {'available_ram_bytes': sum(s['memory']['available'] for s in samples)/len(samples),
                'cpu_percent': sum(sum(s['cpu_per_core'])/len(s['cpu_per_core']) for s in samples)/len(samples)}
    return {'before': means(before), 'after': means(after),
            'note': 'These measurements do not establish whether the user-visible symptom improved; confirm that separately.'}


def inspect_process(pid, created_at):
    process=psutil.Process(pid)
    if abs(process.create_time()-created_at)>.01:
        raise ValueError('The process identity changed; inspect current measurements again.')
    return {'pid':pid,'created_at':created_at,'name':process.name(),'memory':process.memory_info()._asdict(),
            'cpu_percent':process.cpu_percent(interval=.3),'threads':process.num_threads(),
            'action':'read_only','command_line':'not collected'}


def prepare_unload(model):
    from core.model_profiles import PROFILES
    owned={p['tag'] for p in PROFILES.values() if p['tag'].startswith('cortana-local:')}
    if model not in owned:
        raise ValueError('Only an owned Cortana reasoning profile can be unloaded here.')
    loaded=_models()
    match=next((m for m in loaded['models'] if m['name']==model),None)
    if not match:
        raise ValueError('This Cortana model is not loaded.')
    return {'model':model,'_digest':match['digest']}, f"Unload idle Cortana model {model}. It will reload on its next use. No application or foreign model is stopped."


def unload_model(model,_digest=None):
    from core.resource_broker import gpu_slot
    if not _digest:
        raise ValueError('Review the exact loaded model first.')
    with gpu_slot():
        loaded=_models()
        match=next((m for m in loaded['models'] if m['name']==model),None)
        if not match or match['digest']!=_digest:
            raise ValueError('Loaded model state changed; review again.')
        check_cancelled()
        with httpx.Client(timeout=30,trust_env=False) as client:
            response=client.post(settings.ollama_host+'/api/generate',json={'model':model,'keep_alive':0})
            response.raise_for_status()
        after=_models()
        return {'model':model,'unloaded':after['available'] and not any(m['name']==model for m in after['models']),
                'before':match,'after':after,'note':'Run another diagnostic measurement and assess the visible symptom.'}
