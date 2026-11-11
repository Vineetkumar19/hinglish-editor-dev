"""Freeze measured row relationships and independently sampled source motion."""
from pathlib import Path
import json,numpy as np
root=Path(__file__).resolve().parents[2];out=root/'output/caption-two-ae/fidelity-rebuild'
target=root/'editor_plugins/caption-two/profile.json';profile=json.loads(target.read_text('utf8'))
rows=json.loads((out/'row-measurements.json').read_text('utf8'));frames=json.loads((out/'all-frame-measurements.json').read_text('utf8'))['frames'];original=json.loads((root/'hinglish_captions/caption_two_reference.json').read_text('utf8'))['recipes'];checks=[]
for recipe in profile['recipes']:
 slot=recipe.get('source_slot')
 if slot is None:
  recipe['camera_path']=[[0,1,0,0],[1,1,0,0]];continue
 reference=original[slot];sample=next(r for r in rows if r['source_slot']==slot);main=next(r['box'] for r in sample['rows'] if r['id']=='main');width=main[2]-main[0];height=main[3]-main[1]
 optics={}
 for row in sample['rows']:
  if row['id']=='main':continue
  b=row['box'];optics[row['id']]={'x':(b[0]-main[0])/width,'y':(b[1]-main[1])/height,'right':(b[2]-main[0])/width,'score':row['score'],'source_box':b}
  if row['id']=='top_left':recipe['header_size']=row['size']
  if row['id']=='bottom':recipe['footer_size']=row['size'];recipe['footer_font']='regular' if row.get('font')=='regular' else 'bold'
 recipe['optics']=optics;recipe['main_delay']=(min(reference['starts'][i] for row in reference['rows'] if row['role']=='main' for i in row['words'])-reference['starts'][0])/30
 onset=min(reference['starts'][i] for row in reference['rows'] if row['role']=='main' for i in row['words']);complete=max(reference['starts'][i] for row in reference['rows'] if row['role']=='main' for i in row['words'])
 usable=[f for f in frames[max(onset+2,complete+3):reference['end']-3] if f['main_ink_box']]
 tail=usable[-max(3,len(usable)//4):];steady=np.median([f['main_ink_box'] for f in tail],axis=0);basewidth=steady[2]-steady[0];centre=(steady[:2]+steady[2:])/2
 points=[]
 for f in usable[::2]:
  box=np.array(f['main_ink_box']);c=(box[:2]+box[2:])/2;points.append([round((f['frame']-onset)/30,6),round((box[2]-box[0])/basewidth,6),round(float(c[0]-centre[0]),4),round(float(c[1]-centre[1]),4)])
 if points:
  recipe['camera_path']=[[0,recipe['camera'][0][1],points[0][2],points[0][3]]]+points
  colours=[f['core_colour_rgb'] for f in tail if 'core_colour_rgb' in f];recipe['lime_rgb']=np.median(colours,axis=0).round().astype(int).tolist()
  # Odd source frames are independent holdouts, not used as native keys.
  errors=[]
  for f in usable[1::2]:
   t=(f['frame']-onset)/30;pred=[float(np.interp(t,[p[0] for p in points],[p[j] for p in points])) for j in [1,2,3]];box=np.array(f['main_ink_box']);c=(box[:2]+box[2:])/2
   errors.append([abs(pred[0]*basewidth-(box[2]-box[0])),abs(pred[1]-(c[0]-centre[0])),abs(pred[2]-(c[1]-centre[1]))])
  checks.append({'source_slot':slot,'key_frames':len(points),'holdout_frames':len(errors),'mean_abs_pixel_error_width_x_y':np.mean(errors,axis=0).tolist() if errors else [],'initial_before_complete':'Camera extrapolation before complete main-word visibility is not independently verified.'})
profile['fonts']['regular']=['StorylensInterCaption-Regular'];profile['tracking']['regular']=-60
fits=json.loads((out/'effect-edge-fit.json').read_text('utf8'));profile['appearance']={'shadow_y':float(np.median([x['fit']['shadow_y'] for x in fits])),'shadow_blur':float(np.median([x['fit']['shadow_blur'] for x in fits])),'shadow_opacity':float(np.median([x['fit']['coefficients'][2] for x in fits])),'glow_radius':4,'glow_strength':float(np.median([x['fit']['coefficients'][1] for x in fits])),'entry_blur':4,'inference_limit':'Edge fit uses locally estimated background; native effect equivalence remains unverified.'}
profile['reference_measurements']={'frames':507,'row_measurements':'output/caption-two-ae/fidelity-rebuild/row-measurements.json','motion_holdouts':'output/caption-two-ae/fidelity-rebuild/motion-holdouts.json','font_candidates':107,'font_identity_verified':False};profile['revision']=3;profile['motion_policy']='Recipe-specific smooth reference zoom on the group clock; raw XY is analysis data only; glyph-clearance geometry uses a stable complete-group pivot.'
target.write_text(json.dumps(profile,indent=2)+'\n',encoding='utf8');(out/'motion-holdouts.json').write_text(json.dumps(checks,indent=2),encoding='utf8');print(json.dumps(checks))
