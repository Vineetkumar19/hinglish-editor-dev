/* Standalone reference-inspired title rig. Does not save or replace a project. */
$.global.StorylensCameraTitles=function(options){
 options=options||{};
    var result={ok:false,compositions:[],warnings:[]},undo=false,parents=[],inserted=null,destination=null,destinationTime=0,openComp=null,previousDestinationRenderer=null;
    function tr(layer,name){return layer.property('ADBE Transform Group').property(name);}
    function ease(property){
        for(var key=1;key<=property.numKeys;key++){
            property.setInterpolationTypeAtKey(key,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);
            var incoming=property.keyInTemporalEase(key),outgoing=property.keyOutTemporalEase(key),a=[],b=[],d;
            for(d=0;d<incoming.length;d++)a.push(new KeyframeEase(0,58));
            for(d=0;d<outgoing.length;d++)b.push(new KeyframeEase(0,58));
            try{property.setTemporalEaseAtKey(key,a,b);}catch(e){var expected=String(e).match(/Value array does not have ([123]) elements/i);if(!expected)throw e;a=[];b=[];for(d=0;d<Number(expected[1]);d++){a.push(new KeyframeEase(0,58));b.push(new KeyframeEase(0,58));}property.setTemporalEaseAtKey(key,a,b);}
            if(property.isSpatial){var tangent=property.keyInSpatialTangent(key),zero=[];for(d=0;d<tangent.length;d++)zero.push(0);property.setSpatialTangentsAtKey(key,zero,zero);}
        }
    }
    function json(v){
        if(v===null)return 'null';if(typeof v==='string')return '"'+v.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n')+'"';
        if(typeof v==='boolean'||typeof v==='number')return String(v);var a=[],k;
        if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}
        for(k in v)if(v.hasOwnProperty(k))a.push(json(k)+':'+json(v[k]));return '{'+a.join(',')+'}';
    }
    function chooseFont(){
        var candidates=['Montserrat-Black','Montserrat-ExtraBold','Arial-Black','Arial-BoldMT'];
        for(var i=0;i<candidates.length;i++)try{var f=app.fonts.getFontsByPostScriptName(candidates[i]);if(f.length&&!f[0].isSubstitute)return candidates[i];}catch(ignore){}
        result.warnings.push('Use a heavy installed font in Character if the default is substituted.');return 'Arial-BoldMT';
    }
    function comp(name,width,height,parent){
        // Cinema 4D rejects motion-blur writes, even when a new comp already uses that renderer.
        var c=app.project.items.addComp(name,width,height,1,8,30);c.parentFolder=parent;c.bgColor=[0,0,0];c.resolutionFactor=[2,2];return c;
    }
    function null3D(c,name,assets){var l=c.layers.addNull(8);l.name=name;l.threeDLayer=true;l.source.parentFolder=assets;tr(l,'ADBE Anchor Point').setValue([0,0,0]);return l;}
    function cover(keys,width,height){
        function norm(a){var n=Math.sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]);return [a[0]/n,a[1]/n,a[2]/n];}
        function cross(a,b){return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];}
        var scale=1,positions=[];
        for(var i=0;i<keys.length;i++){positions.push(keys[i].p);if(i)for(var j=1;j<8;j++){var a=keys[i-1].p,b=keys[i].p,t=j/8;positions.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t]);}}
        for(var i=0;i<positions.length;i++){
            var p=[positions[i][0],positions[i][1],positions[i][2]-2500],f=norm([width/2-p[0],height/2-p[1],-180-p[2]]),r=norm(cross(f,[0,-1,0])),d=cross(f,r);
            for(var x=-1;x<=1;x+=2)for(var y=-1;y<=1;y+=2){
                var ray=[f[0]+r[0]*x*width/3500+d[0]*y*height/3500,f[1]+r[1]*x*width/3500+d[1]*y*height/3500,f[2]+r[2]*x*width/3500+d[2]*y*height/3500];
                var distance=(400-p[2])/ray[2],px=p[0]+ray[0]*distance,py=p[1]+ray[1]*distance;
                scale=Math.max(scale,Math.abs(px-width/2)/(width/2),Math.abs(py-height/2)/(height/2));
            }
        }return scale*102;
    }
    try{
        if(!app.project)app.newProject();
        if(options.insert===true){destination=app.project.activeItem;if(!(destination instanceof CompItem))throw Error("Open a composition first.");previousDestinationRenderer=destination.renderer;$.global.StorylensSolidTitles.rendererFor(destination);destinationTime=destination.time;if(destination.duration-destinationTime<.6)throw Error("Move the playhead earlier in the composition.");}
        var selected=app.project.selection||[],source=selected.length===1&&selected[0] instanceof FootageItem&&selected[0].hasVideo&&selected[0].width>0&&selected[0].height>0?selected[0]:null;
        var font=chooseFont();if(options.manageUndo!==false){app.beginUndoGroup('Create 3D Camera Titles');undo=true;}
        var family=$.global.StorylensCaptionFolders.family('3D1',parents);var root=app.project.items.addFolder(['Boost','Professional Look','In a Few Clicks','Stand Out'][options.index]||'Camera Titles');root.parentFolder=family;result.folder_id=String(root.id);root.comment=options.marker?options.marker+' building':'';var assets=app.project.items.addFolder('Controls and depth');assets.parentFolder=root;
        var footageFolder=app.project.items.addFolder('YOUR FOOTAGE');footageFolder.parentFolder=root;
        var horizontal=comp('YOUR FOOTAGE - Horizontal',1920,1080,footageFolder),vertical=comp('YOUR FOOTAGE - Vertical',1080,1920,footageFolder);
        if(source){
            var holders=[horizontal,vertical];for(var h=0;h<holders.length;h++){var shot=holders[h].layers.add(source),fit=Math.max(holders[h].width/source.width,holders[h].height/source.height)*100;tr(shot,'ADBE Scale').setValue([fit,fit]);}
        }
        var presets=[
            {name:'01 BOOST',main:'BOOST',sub:'PROPERTY LISTINGS',yellow:0,mainSize:240,subSize:80},
            {name:'02 PROFESSIONAL LOOK',main:'PROFESSIONAL',sub:'LOOK',yellow:1,mainSize:170,subSize:225},
            {name:'03 IN A FEW CLICKS',main:'IN A FEW',sub:'CLICKS',yellow:1,mainSize:210,subSize:290},
            {name:'04 STAND OUT',main:'STAND OUT',sub:'ON SOCIAL MEDIA',yellow:0,mainSize:215,subSize:100}
        ];
        for(var pi=0;pi<presets.length;pi++)for(var formatIndex=0;formatIndex<2;formatIndex++){
            if(typeof options.index==='number'&&pi!==options.index)continue;
 if(options.format&&(formatIndex===1?'vertical':'horizontal')!==options.format)continue;
 var preset=presets[pi];if(options.rows){preset.main=options.rows[0].text;preset.sub=options.rows[1].text;}
 var isVertical=formatIndex===1,width=isVertical?1080:1920,height=isVertical?1920:1080,factor=width/1920;
            var c=comp('TITLE - 3D1 '+preset.name+' - '+(isVertical?'Vertical':'Horizontal'),width,height,root),dolly=null3D(c,'CAMERA MOVE - Edit these keys',assets),target=null3D(c,'CAMERA TARGET',assets);
            tr(target,'ADBE Position').setValue([width/2,height/2,-180]);target.shy=true;
            var keys=[{t:0,p:[width/2-70*factor,height/2-20*factor,-200]},
                {t:1.7,p:[width/2+45*factor,height/2+8*factor,420]},
                {t:5.8,p:[width/2+70*factor,height/2+14*factor,440]},
                {t:8,p:[width/2-55*factor,height/2-15*factor,-200]}];
            for(var k=0;k<keys.length;k++)tr(dolly,'ADBE Position').setValueAtTime(keys[k].t,keys[k].p);ease(tr(dolly,'ADBE Position'));
            var camera=c.layers.addCamera('CAMERA - Near and far',[width/2,height/2]);camera.parent=dolly;camera.autoOrient=AutoOrientType.CAMERA_OR_POINT_OF_INTEREST;
            tr(camera,'ADBE Position').setValue([0,0,-2500]);tr(camera,'ADBE Anchor Point').expression='var t=thisComp.layer("CAMERA TARGET");parent.fromWorld(t.toWorld(t.anchorPoint));';
            camera.property('ADBE Camera Options Group').property('ADBE Camera Zoom').setValue(1750);camera.property('ADBE Camera Options Group').property('ADBE Camera Depth of Field').setValue(0);
            var video=c.layers.add(isVertical?vertical:horizontal);video.name='YOUR FOOTAGE';video.threeDLayer=true;
            tr(video,'ADBE Position').setValue([width/2,height/2,400]);var scale=cover(keys,width,height);tr(video,'ADBE Scale').setValue([scale,scale,scale]);video.moveToEnd();
            var title=null3D(c,'TITLE POSITION - Move both lines',assets);tr(title,'ADBE Position').setValue([width/2,height/2,-260]);tr(title,'ADBE Orientation').setValue([4,-13,0]);
            var depthControl=title.property('ADBE Effect Parade').addProperty('ADBE Slider Control');depthControl.name='DEPTH - Letter sides';depthControl.property('ADBE Slider Control-0001').setValue(96*factor);
            var opacity=tr(title,'ADBE Opacity');opacity.setValueAtTime(0,0);opacity.setValueAtTime(.32,100);opacity.setValueAtTime(7.25,100);opacity.setValueAtTime(8,0);ease(opacity);
            var names=['EDIT - MAIN','EDIT - SUBTITLE'],strings=[preset.main,preset.sub],sizes=[preset.mainSize,preset.subSize],front=[];
            if(isVertical&&pi===0)sizes=[270,94];
            for(var row=0;row<2;row++){
                var l=c.layers.addText(strings[row]);l.name=names[row];l.threeDLayer=true;l.parent=title;
                var text=l.property('ADBE Text Properties').property('ADBE Text Document'),doc=text.value;doc.font=font;doc.fontSize=sizes[row]*factor;doc.applyFill=true;doc.fillColor=row===preset.yellow?[1,.86,0]:[1,1,1];doc.applyStroke=false;doc.justification=ParagraphJustification.CENTER_JUSTIFY;doc.tracking=-15;text.setValue(doc);
                tr(l,'ADBE Anchor Point').expression='var r=sourceRectAtTime(0,false);[r.left+r.width/2,r.top+r.height/2,0]';
                tr(l,'ADBE Scale').expression='var r=sourceRectAtTime(0,false);var s=Math.min(1,thisComp.width*.80/Math.max(1,r.width))*100;[s,s,s]';
                tr(l,'ADBE Opacity').expression='parent.opacity*ease(time,'+(.12+row*.24)+','+(.42+row*.24)+',0,1)';
                l.comment='Edit text in this layer. Width fitting and the other row update automatically.';front.push(l);
            }
            var gap=Math.round(width*.020);
            tr(front[0],'ADBE Position').expression='var l=thisComp.layer("EDIT - SUBTITLE");var h=l.sourceRectAtTime(0,false).height*l.scale[1]/100;var slide=ease(time,.12,.67,'+(80*factor)+',0);[0,-(h+'+gap+')/2+slide,0]';
            tr(front[1],'ADBE Position').expression='var l=thisComp.layer("EDIT - MAIN");var h=l.sourceRectAtTime(0,false).height*l.scale[1]/100;var slide=ease(time,.36,.91,'+(80*factor)+',0);[0,(h+'+gap+')/2+slide,24]';
            video.moveToEnd();front[0].moveToBeginning();front[1].moveToBeginning();c.hideShyLayers=true;c.time=2;
            c.comment='Editable native extruded 3D text. Collapsed placement uses the containing composition camera. No motion tracking analysis has been applied to the footage.';
            var solidRenderer=$.global.StorylensSolidTitles.prepare(c,options.depth||100,true,result.warnings);
            if(typeof options.index==='number')c.comment+=' [Storylens 3D1 '+['boost','look','clicks','standout'][options.index]+']';
            if(options.sound_fx!==false)$.global.StorylensCaptionSounds.add(c,0,$.global.StorylensCaptionSounds.events(options.sound_mode,options.delay===undefined ? .12 : options.delay),root);$.global.StorylensCaptionSounds.mark(c,options.sound_mode||'pop_click',options.sound_fx!==false,'');
            result.compositions.push({name:c.name,id:String(c.id),font:font,footageScale:scale,cameraKeys:keys.length,depth:options.depth||100,slicesPerLine:0,renderer:solidRenderer});
        }
        if(options.insert===true){
            if(result.compositions.length!==1)throw Error('Choose one title and format before inserting.');
            var master=null;for(var mi=1;mi<=app.project.numItems;mi++)if(String(app.project.item(mi).id)===result.compositions[0].id)master=app.project.item(mi);
            if(!master)throw Error('The new title precomp could not be located.');
            inserted=destination.layers.add(master);inserted.name=master.name;destination.renderer=solidRenderer;inserted.threeDLayer=true;inserted.collapseTransformation=true;inserted.startTime=destinationTime;inserted.inPoint=destinationTime;inserted.outPoint=Math.min(destination.duration,destinationTime+master.duration);
            var fit=Math.min(destination.width/master.width,destination.height/master.height)*100;tr(inserted,'ADBE Scale').setValue([fit,fit]);result.placed=1;
        }
        result.parent_ids=[];for(var ri=0;ri<parents.length;ri++)result.parent_ids.push(String(parents[ri].id));
        root.comment=options.marker?options.marker+(options.deferPlacement?' building':' done'):'';result.ok=true;result.renderer=solidRenderer;result.depth='Native extruded text geometry; Cinema 4D; collapsed 3D precomp';result.footageAdded=!!source;
        // Open the first complete template; no project save or automatic render.
        if(options.insert===true)openComp=destination;else if(!options.deferPlacement)for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(String(item.id)===result.compositions[0].id){openComp=item;break;}}
    }catch(error){try{if(inserted)inserted.remove();if(destination&&previousDestinationRenderer!==null)destination.renderer=previousDestinationRenderer;if(root)root.remove();}catch(ignoreCleanup){}$.global.StorylensCaptionFolders.cleanup(parents);result.error=String(error);result.line=error.line;}
    finally{
        if(undo)app.endUndoGroup();

    }
    if(result.ok&&openComp)try{openComp.openInViewer();}catch(viewError){result.warnings.push('The title was created. Return to your composition to use it.');}
    return result;
};
