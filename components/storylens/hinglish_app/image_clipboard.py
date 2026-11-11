"""One explicit clipboard read. No keyboard listener, screenshot or polling."""
import io
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin
from PIL import Image,ImageGrab

def read_image(reader=None):
    image=(reader or ImageGrab.grabclipboard)()
    if not isinstance(image,Image.Image):
        raise ValueError('Image download: no image is available on the clipboard. Copy one image, then paste again.')
    if image.width*image.height>60_000_000:raise ValueError('Image download: choose an image smaller than 60 megapixels.')
    buffer=io.BytesIO();image.save(buffer,'PNG')
    if buffer.tell()>25*1024**2:raise ValueError('Image download: choose an image smaller than 25 MB.')
    return buffer.getvalue()

def image_address(html):
    """Read one copied IMG, never execute markup or infer a different image."""
    class Parser(HTMLParser):
        def __init__(self):super().__init__();self.images=[]
        def handle_starttag(self,tag,attrs):
            if tag.lower()=='img':
                src=dict(attrs).get('src','')
                if src and src not in self.images:self.images.append(src)
    parser=Parser();parser.feed(html)
    if len(parser.images)!=1:raise ValueError('Image download: copy one image first.')
    match=re.search(r'^SourceURL:(https?://[^\r\n]+)',html,re.M)
    url=urljoin(match[1] if match else '',parser.images[0])
    if not url.startswith(('http://','https://')):raise ValueError('Image download: no usable copied image is available.')
    return url

def read_html_address():
    # Only the image markup format, on an explicit Paste/Ctrl+B request. No
    # generic text-clipboard inspection, keyboard hooks, polling or screenshots.
    if sys.platform!='win32':raise ValueError('Image download: no image on the clipboard.')
    import ctypes as C
    from ctypes import wintypes as W
    user,kernel=C.WinDLL('user32'),C.WinDLL('kernel32')
    user.RegisterClipboardFormatW.argtypes=[W.LPCWSTR];user.RegisterClipboardFormatW.restype=W.UINT
    user.OpenClipboard.argtypes=[W.HWND];user.OpenClipboard.restype=W.BOOL
    user.GetClipboardData.argtypes=[W.UINT];user.GetClipboardData.restype=W.HANDLE
    kernel.GlobalLock.argtypes=[W.HANDLE];kernel.GlobalLock.restype=C.c_void_p
    kernel.GlobalUnlock.argtypes=[W.HANDLE]
    kernel.GlobalSize.argtypes=[W.HANDLE];kernel.GlobalSize.restype=C.c_size_t
    if not user.OpenClipboard(None):raise ValueError('Image download: the clipboard is busy; paste again.')
    try:
        handle=user.GetClipboardData(user.RegisterClipboardFormatW('HTML Format'))
        size=kernel.GlobalSize(handle) if handle else 0
        if not 0<size<=4*1024**2:raise ValueError('Image download: no image on the clipboard.')
        pointer=kernel.GlobalLock(handle)
        if not pointer:raise ValueError('Image download: no image on the clipboard.')
        try:html=C.string_at(pointer,size).rstrip(b'\0').decode('utf8',errors='replace')
        finally:kernel.GlobalUnlock(handle)
    finally:user.CloseClipboard()
    return image_address(html)
