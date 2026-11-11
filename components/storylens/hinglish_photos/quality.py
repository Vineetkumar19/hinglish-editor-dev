"""Resolution policy: preserve each reference tile, with optional stricter HD targets."""
def meets_quality(row,min_edge=0):
    if min_edge==0:return row.get('width',0)>0 and row.get('height',0)>0
    box=row.get('box') or [0,0,1,1];required_w,required_h=box[2:4]
    width,height=row.get('width',0),row.get('height',0)
    match=row.get('match') or {}
    detail_w=row.get('effective_width') or match.get('effective_width') or width
    detail_h=row.get('effective_height') or match.get('effective_height') or height
    return (width>=required_w and height>=required_h and detail_w+2>=required_w and detail_h+2>=required_h
        and max(min(width,detail_w),min(height,detail_h))+2>=min_edge)
