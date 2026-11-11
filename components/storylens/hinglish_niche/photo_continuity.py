"""Review actual projected photo geometry, excluding decorative backgrounds."""
import math

TRACE_JS='''() => [...document.querySelectorAll('img')].map((image,index)=>{
  if(image.closest('.archive-background,.archive-bg-photo,.archive-bg-echo'))return null;
  let opacity=1;for(let n=image;n&&n.nodeType===1;n=n.parentElement){
    const style=getComputedStyle(n);if(style.display==='none'||style.visibility==='hidden')return null;
    opacity*=Number(style.opacity);
  }
  const r=image.getBoundingClientRect(),w=innerWidth,h=innerHeight;
  const visible=Math.max(0,Math.min(w,r.right)-Math.max(0,r.left))*Math.max(0,Math.min(h,r.bottom)-Math.max(0,r.top));
  if(opacity<.1||visible<w*h*.015)return null;
  return {id:index,src:image.src,x:r.x/w,y:r.y/h,width:r.width/w,height:r.height/h};
}).filter(Boolean)'''

def review(traces,fps,quiet_limit=.75,settle=.65):
    previous={};quiet={};born={};ranges=[];tracked=0;dt=1/float(fps)
    for index,items in enumerate(traces):
        t=index*dt;current={p['id']:p for p in items}
        for key,p in current.items():
            if key not in previous:born[key]=t;continue
            before=previous[key]
            dx=(p['x']+p['width']/2)-(before['x']+before['width']/2)
            dy=(p['y']+p['height']/2)-(before['y']+before['height']/2)
            pan=math.hypot(dx,dy)/dt
            zoom=max(abs(p['width']/max(before['width'],1e-8)-1),abs(p['height']/max(before['height'],1e-8)-1))/dt
            moving=pan>.0003 or zoom>.002 or p['src']!=before['src']
            if t-born[key]<settle:continue
            tracked+=1
            if moving:
                if key in quiet and t-quiet[key]>=quiet_limit:ranges.append({'image':key,'start':quiet[key],'end':t})
                quiet.pop(key,None)
            elif key not in quiet:quiet[key]=t
        for key in set(previous)-set(current):
            if key in quiet and t-quiet[key]>=quiet_limit:ranges.append({'image':key,'start':quiet[key],'end':t})
            quiet.pop(key,None);born.pop(key,None)
        previous=current
    end=len(traces)*dt
    for key,start in quiet.items():
        if end-start>=quiet_limit:ranges.append({'image':key,'start':start,'end':end})
    return {'available':tracked>0,'tracked_image_pairs':tracked,'needs_review':bool(ranges),
        'stationary_photo_ranges':ranges,'background_photos_excluded':True,
        'scope':'Projected foreground image geometry after entry settling; real clip source changes count as content motion. Masks, internal canvas artwork and physical 3D depth require separate review.',
        'warnings':['A foreground photograph stays still after its entrance; review camera or image movement.'] if ranges else []}
