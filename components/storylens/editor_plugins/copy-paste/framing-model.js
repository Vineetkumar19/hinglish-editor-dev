/* Optional subject-framing math; core Copy/Undo do not load this file. */
var SLCopyPasteFramingModel=(function(M){
    function reframe(w, h, aspect, sw, sh, sourceAspect, analysis, viewport) {
        var full = M.fit(w,h,aspect,sw,sh,sourceAspect,'fill') / 100;
        var v = viewport || [0,0,w,h], l=Math.max(0,v[0]),t=Math.max(0,v[1]),r=Math.min(w,v[2]),b=Math.min(h,v[3]);
        if (!(r>l&&b>t)) M.fail('copy_paste_template','This picture frame has no stable visible area. Choose a separate scene.');
        var faces=analysis&&analysis.faces||[], box=[1,1,0,0], i,k,face,found=false;
        for(i=0;i<faces.length;i++) {
            face=faces[i].box;if(!face||face.length!==4)continue;
            for(k=0;k<4;k++)if(typeof face[k]!=='number'||!isFinite(face[k])||face[k]<0||face[k]>1)M.fail('copy_paste_media','The picture framing data is invalid. Copy the media again.');
            if(face[2]<=face[0]||face[3]<=face[1])continue;
            box=[Math.min(box[0],face[0]),Math.min(box[1],face[1]),Math.max(box[2],face[2]),Math.max(box[3],face[3])];found=true;
        }
        // With no reliable face, keep the whole photo rather than inventing a subject.
        if(!found)box=[0,0,1,1];
        var par=sourceAspect/aspect,vw=r-l,vh=b-t,margin=found?Math.min(vw,vh)*.025:0;
        var cover=Math.max(vw/(sw*par),vh/sh);
        var scale=Math.min(cover,(vw-2*margin)/((box[2]-box[0])*sw*par),(vh-2*margin)/((box[3]-box[1])*sh));
        var sx=scale*par,sy=scale,position=[],dims=[sw,sh],starts=[l,t],ends=[r,b],factors=[sx,sy];
        for(k=0;k<2;k++) {
            var lo=starts[k]+margin-(box[k]*dims[k]-dims[k]/2)*factors[k];
            var hi=ends[k]-margin-(box[k+2]*dims[k]-dims[k]/2)*factors[k];
            var clo=ends[k]-dims[k]*factors[k]/2,chi=starts[k]+dims[k]*factors[k]/2;
            if(Math.max(lo,clo)<=Math.min(hi,chi)){lo=Math.max(lo,clo);hi=Math.min(hi,chi);}
            var aim=(starts[k]+ends[k])/2-((box[k]+box[k+2])/2-.5)*dims[k]*factors[k];
            position[k]=Math.max(lo,Math.min(hi,aim));
        }
        var background=position[0]-sw*sx/2>.001||position[0]+sw*sx/2<w-.001||position[1]-sh*sy/2>.001||position[1]+sh*sy/2<h-.001;
        return {scale:scale*100,position:position,background:background,background_scale:full*100,subject_bounds:box,
            viewport:[l,t,r,b],method:found?'face-safe':'whole-image',video_sampled:!!(analysis&&analysis.video_sampled)};
    }
    return {reframe:reframe};
})(typeof SLCopyPasteModel!=='undefined'?SLCopyPasteModel:require('./model.js'));
if(typeof module!=='undefined'&&module.exports)module.exports=SLCopyPasteFramingModel;
