"""Observe word geometry through the *existing* caption renderer.

The capture context is local to the exporting thread. Normal rendering never
changes. Only geometry, font identity and animation values leave this module;
the native editor receives text graphics, not pictures of the words.
"""
from contextvars import ContextVar
from contextlib import contextmanager
import math

_active = ContextVar('caption_scene_capture', default=False)
_installed = False


def active():
    return _active.get()


def _rows(image):
    return getattr(image, '_storylens_words', [])


def _move(rows, a=1, b=0, c=0, d=0, e=1, f=0):
    result=[]
    for word in rows:
        row=dict(word)
        x,y=row['x'],row['y']
        row['x'],row['y']=a*x+b*y+c,d*x+e*y+f
        # All current caption engines use axis-aligned scaling/translations.
        sx,sy=math.hypot(a,d),math.hypot(b,e)
        row['sx']*=sx;row['sy']*=sy
        row['blur']=row.get('blur',0)*math.sqrt((sx*sx+sy*sy)/2)
        result.append(row)
    return result


def tag(image,index,text,font,x,baseline,tracking=0,color='#FFFFFF',gradient=None,weight=None,alpha=1,outline=False,stroke_width=0,stroke_color=None):
    if not active():return image
    # Cached renderer assets belong to the renderer. Annotate a copy so an
    # export cannot leak capture metadata or mutate a later normal preview.
    image=image.copy()
    boxes=[]
    for j,char in enumerate(text):
        if char.isspace():continue
        box=font.getbbox(char);offset=font.getlength(text[:j])+j*font.size*tracking
        boxes.append((box[0]+offset,box[1],box[2]+offset,box[3]))
    left=min((b[0] for b in boxes),default=0);right=max((b[2] for b in boxes),default=0)
    top=min((b[1] for b in boxes),default=0);bottom=max((b[3] for b in boxes),default=0)
    row={'index':index,'text':text,'font_path':str(font.path),'weight':weight,
         'size_px':font.size,'tracking':tracking,'color':color,'gradient':gradient,
         'x':x+(left+right)/2,'y':baseline-font.getmetrics()[0]+(top+bottom)/2,
         'sx':1.,'sy':1.,'alpha':alpha,'outline':outline,
         'stroke_width':stroke_width or (max(1,round(font.size*.012)) if outline else 0),
         'stroke_color':stroke_color}
    image._storylens_words=[row]
    return image


def tag_draw(draw,index,text,font,xy,color='#FFFFFF',alpha=1,outline=False,stroke_width=0,stroke_color=None):
    if not active():return
    image=draw._image
    tagged=tag(image,index,text,font,xy[0],xy[1]+font.getmetrics()[0],color=color,alpha=alpha,outline=outline,stroke_width=stroke_width,stroke_color=stroke_color)
    image._storylens_words=_rows(image)+_rows(tagged)


def _install():
    global _installed
    if _installed:return
    from PIL import Image
    cls=Image.Image
    for name in ('copy','convert','crop','resize','transform','filter','getchannel','point'):
        original=getattr(cls,name)
        def wrapped(self,*args,_name=name,_original=original,**kwargs):
            output=_original(self,*args,**kwargs)
            if not active():return output
            rows=_rows(self)
            if rows:
                if _name=='crop':
                    box=args[0] if args else kwargs.get('box')
                    output._storylens_words=_move(rows,c=-box[0],f=-box[1]) if box else _move(rows)
                elif _name=='resize':
                    size=args[0] if args else kwargs['size']
                    output._storylens_words=_move(rows,a=size[0]/self.width,e=size[1]/self.height)
                elif _name=='transform':
                    method=args[1] if len(args)>1 else kwargs.get('method')
                    data=args[2] if len(args)>2 else kwargs.get('data')
                    if method!=Image.Transform.AFFINE:
                        raise ValueError('This caption uses a transform the editable importer cannot preserve. Choose the finished video for this effect.')
                    a,b,c,d,e,f=data;det=a*e-b*d
                    output._storylens_words=_move(rows,e/det,-b/det,(b*f-e*c)/det,-d/det,a/det,(d*c-a*f)/det)
                else:
                    output._storylens_words=_move(rows)
                    if _name=='filter' and args:
                        from PIL import ImageFilter
                        if isinstance(args[0],ImageFilter.GaussianBlur):
                            radius=args[0].radius
                            if isinstance(radius,tuple):radius=sum(radius)/len(radius)
                            for row in output._storylens_words:row['blur']=math.hypot(row.get('blur',0),radius)
            if _name=='getchannel' and args and args[0]=='A':
                output._storylens_alpha=1.
            if _name=='point' and hasattr(self,'_storylens_alpha'):
                func=args[0] if args else kwargs.get('lut')
                factor=(func(255)/255 if callable(func) else func[255]/255)
                output._storylens_alpha=self._storylens_alpha*factor
            return output
        setattr(cls,name,wrapped)
    original_alpha=cls.alpha_composite
    def alpha_composite(self,im,dest=(0,0),source=(0,0)):
        result=original_alpha(self,im,dest,source)
        if active() and _rows(im):
            self._storylens_words=_rows(self)+_move(_rows(im),c=dest[0]-source[0],f=dest[1]-source[1])
        return result
    cls.alpha_composite=alpha_composite
    original_pair=Image.alpha_composite
    def pair(a,b):
        result=original_pair(a,b)
        if active():result._storylens_words=_move(_rows(a))+_move(_rows(b))
        return result
    Image.alpha_composite=pair
    original_paste=cls.paste
    def paste(self,im,box=None,mask=None):
        result=original_paste(self,im,box,mask)
        if active() and isinstance(im,Image.Image) and _rows(im):
            self._storylens_words=_rows(self)+_move(_rows(im),c=(box or (0,0))[0],f=(box or (0,0))[1])
        return result
    cls.paste=paste
    original_putalpha=cls.putalpha
    def putalpha(self,alpha):
        result=original_putalpha(self,alpha)
        if active() and _rows(self) and hasattr(alpha,'_storylens_alpha'):
            rows=_move(_rows(self))
            for row in rows:row['alpha']*=alpha._storylens_alpha
            self._storylens_words=rows
        return result
    cls.putalpha=putalpha
    _installed=True


@contextmanager
def capture():
    _install();token=_active.set(True)
    try:yield
    finally:_active.reset(token)


def words(image):
    # Glow is composited before the sharp copy. Keep the sharp, final word
    # rather than producing two overlapping editable copies of every letter.
    result={}
    for row in _rows(image):
        result[(row['index'],row.get('outline',False))]=row
    return list(result.values())
