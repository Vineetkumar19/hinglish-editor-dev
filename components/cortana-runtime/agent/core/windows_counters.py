"""Read-only Windows performance counters, with explicit missing sensors."""
import math


class WindowsCounters:
    paths = {
        'disk_idle_percent':r'\PhysicalDisk(_Total)\% Idle Time',
        'disk_transfer_seconds':r'\PhysicalDisk(_Total)\Avg. Disk sec/Transfer',
        'disk_queue_length':r'\PhysicalDisk(_Total)\Current Disk Queue Length',
        'committed_bytes':r'\Memory\Committed Bytes',
        'commit_limit_bytes':r'\Memory\Commit Limit',
        'pages_per_second':r'\Memory\Pages/sec',
        'page_reads_per_second':r'\Memory\Page Reads/sec',
    }

    def __init__(self):
        self.query=None
        self.counters={}
        self.missing={}
        try:
            import win32pdh
            self.pdh=win32pdh
            self.query=win32pdh.OpenQuery()
            for name,path in self.paths.items():
                try:
                    self.counters[name]=win32pdh.AddEnglishCounter(self.query,path)
                except Exception as exc:
                    self.missing[name]=type(exc).__name__
            win32pdh.CollectQueryData(self.query)
        except Exception as exc:
            self.missing['query']=type(exc).__name__
            self.close()

    def sample(self):
        values={}
        missing=dict(self.missing)
        if self.query is not None:
            try:
                self.pdh.CollectQueryData(self.query)
                for name,counter in self.counters.items():
                    try:
                        value=self.pdh.GetFormattedCounterValue(counter,self.pdh.PDH_FMT_DOUBLE)[1]
                        if not math.isfinite(value):
                            raise ValueError('Nonfinite counter')
                        values[name]=value
                    except Exception as exc:
                        missing[name]=type(exc).__name__
            except Exception as exc:
                missing['sample']=type(exc).__name__
        if 'disk_idle_percent' in values:
            values['disk_active_percent']=max(0,min(100,100-values['disk_idle_percent']))
        if 'disk_transfer_seconds' in values:
            values['disk_average_transfer_ms']=values['disk_transfer_seconds']*1000
        return {'available':bool(values),'values':values,'missing':missing,
                'scope':'Windows PhysicalDisk(_Total) and Memory counters; aggregate across drives'}

    def close(self):
        if self.query is not None:
            self.pdh.CloseQuery(self.query)
            self.query=None

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()
