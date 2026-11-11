"""Machine-bound local secrets. Windows DPAPI uses current-user scope, never machine-wide scope."""
import ctypes
from ctypes import wintypes
import hashlib
import os
import subprocess
import re
from pathlib import Path

MAGIC=b'HE-DPAPI-2\0'


def hardware_hash(test_folder=None):
    if test_folder is not None:
        identity='isolated-test:'+str(Path(test_folder).resolve())
    elif os.name=='nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
            machine=winreg.QueryValueEx(key,'MachineGuid')[0]
        # Raw identifiers never leave the computer. DPAPI also binds to this
        # Windows user; the digest supplements its protection against copying.
        if not isinstance(machine,str) or len(machine)<16:raise ValueError('Windows machine identity is unavailable.')
        powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        result=subprocess.run([str(powershell),'-NoProfile','-NonInteractive','-Command',
                    '[string](Get-CimInstance -ClassName Win32_ComputerSystemProduct -ErrorAction Stop).UUID'],
                    check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=12,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        firmware=result.stdout.strip().lower()
        if not re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',firmware) or set(firmware.replace('-',''))<={'0','f'}:
            raise ValueError('The computer firmware identity is unavailable. Contact Support.')
        identity='windows:'+machine.lower()+':firmware:'+firmware
    else:raise ValueError('The commercial desktop license currently supports Windows only.')
    return hashlib.sha256(('hinglish-device-v2:'+identity).encode()).hexdigest()


class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def _blob(value):
    buffer=ctypes.create_string_buffer(value)
    return Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte))),buffer


def _dpapi(value,entropy,decrypt=False):
    if os.name!='nt':raise ValueError('Windows data protection is required.')
    crypto=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    original,buffer=_blob(value);extra,extra_buffer=_blob(entropy);result=Blob()
    protect=crypto.CryptUnprotectData if decrypt else crypto.CryptProtectData
    protect.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    protect.restype=wintypes.BOOL;kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    # UI_FORBIDDEN only. LOCAL_MACHINE would weaken the user binding.
    if not protect(ctypes.byref(original),None,ctypes.byref(extra),None,None,1,ctypes.byref(result)):
        raise ValueError('This activation belongs to another Windows user or computer. Contact Support.')
    try:return ctypes.string_at(result.data,result.size)
    finally:kernel.LocalFree(ctypes.cast(result.data,ctypes.c_void_p))


class DeviceVault:
    def __init__(self,folder,*,test_mode=False):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.test_mode=test_mode;self.hardware_hash=hardware_hash(self.folder if test_mode else None)
        if not test_mode and os.name!='nt':raise ValueError('Windows is required for this release.')
        if os.name=='nt':
            identity=os.environ.get('USERDOMAIN','')+'\\'+os.environ['USERNAME']
            subprocess.run(['icacls',str(self.folder),'/inheritance:r','/grant:r',identity+':(OI)(CI)F'],
                           check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        else:self.folder.chmod(0o700)

    def encode(self,value):
        if self.test_mode:return b'HE-TEST-ONLY\0'+value
        return MAGIC+_dpapi(value,('hinglish-v2:'+self.hardware_hash).encode())

    def decode(self,value):
        if self.test_mode and value.startswith(b'HE-TEST-ONLY\0'):return value[len(b'HE-TEST-ONLY\0'):]
        if not value.startswith(MAGIC):raise ValueError('Legacy activation must be replaced through Support.')
        return _dpapi(value[len(MAGIC):],('hinglish-v2:'+self.hardware_hash).encode(),decrypt=True)

    def read(self,name):return self.decode((self.folder/name).read_bytes())

    def write(self,name,value,*,exclusive=False):
        import uuid
        target=self.folder/name
        if exclusive:
            with target.open('xb') as handle:handle.write(self.encode(value))
        else:
            temporary=self.folder/(uuid.uuid4().hex+'.tmp')
            try:
                with temporary.open('xb') as handle:handle.write(self.encode(value))
                temporary.replace(target)
            finally:temporary.unlink(missing_ok=True)
        if os.name!='nt':target.chmod(0o600)
