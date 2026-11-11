/* Editable graphics plans. User-entered data is never evaluated as code. */
(function(root){
 var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,n=m.number,c=m.choice;
 if(typeof module!=='undefined'&&module.exports)require('./typography-model.js');
 function text(id,label,value,max,multi){return {id:id,label:label,type:'text',value:value,maxLength:max||160,multiline:!!multi};}
 var duration=n('duration','Duration (s)',5,1,60,.1),accent={id:'color',label:'Accent',type:'color',value:'#d9e56c'},x=n('x','Horizontal position (%)',50,0,100,1),y=n('y','Vertical position (%)',50,0,100,1);
 m.register({id:'annotations',name:'Shapes & Annotations'},[
 {number:37,id:'arrow',name:'Animated Arrow',help:'Editable arrow path with draw-on animation. Move the precomp or edit the path points.',settings:[duration,accent,n('angle','Angle (degrees)',0,-180,180,1)]},
 {number:38,id:'callout',name:'Callout',help:'A label, leader line and target dot. Edit the label or move the target in its precomp.',settings:[duration,accent,text('title','Label','Detail')]},
 {number:39,id:'highlight',name:'Highlight',help:'A translucent highlighter bar over your footage. Adjust its position, size and colour.',settings:[duration,accent,x,y,n('width','Width (%)',50,1,95,1),n('height','Height (%)',5,1,50,1)]},
 {number:40,id:'progress',name:'Progress Bar',help:'An editable progress bar animates to the chosen percentage.',settings:[duration,accent,n('value','Progress (%)',75,0,100,1)]},
 {number:41,id:'timer',name:'Timer',help:'Native editable counter with start value and count direction.',settings:[duration,text('title','Label','TIME'),n('value','Start (seconds)',60,0,86400,1),c('direction','Count','down',['down','up'])]},
 {number:42,id:'chart',name:'Bar Chart',help:'One label: value per line. Values must be nonnegative; up to 12 bars.',settings:[duration,accent,text('title','Title','Comparison'),text('data','Data','First: 10\nSecond: 20\nThird: 15',1000,true)]}
 ]);
 m.register({id:'documentary',name:'Documentary Tools'},[
 {number:43,id:'document-highlight',name:'Document Highlighter',help:'A marker strip and optional annotation for a document already on your timeline.',settings:[duration,accent,text('title','Annotation','Important detail'),x,y,n('width','Width (%)',60,1,95,1)]},
 {number:44,id:'focus-zoom',name:'Focus Zoom',help:'Zoom the selected layer around a chosen point. Tweak its framing after applying.',settings:[duration,n('amount','Zoom (%)',125,100,300,1),x,y]},
 {number:45,id:'photo-pan',name:'Photo Pan & Zoom',help:'Slow movement and scale on selected photos. Check that the photo covers the frame.',settings:[duration,n('amount','End scale (%)',112,100,200,1),n('distance','Horizontal travel (px)',80,-1000,1000,1)]},
 {number:46,id:'archival',name:'Archival Look',help:'Editable monochrome/sepia treatment, contrast and grain.',settings:[n('amount','Strength (%)',70,0,100,1),n('grain','Grain (%)',4,0,30,.1)]},
 {number:47,id:'history-timeline',name:'Historical Timeline',help:'One year: event per line. Creates editable dates, labels and timeline markers.',settings:[duration,accent,text('title','Title','Timeline'),text('data','Year: event','2000: First event\n2010: Second event\n2020: Third event',1400,true)]},
 {number:48,id:'map-route',name:'Map Route',help:'A route overlay for your existing map. Edit the native path endpoints; no map download is performed.',settings:[duration,accent,text('title','Start','Start'),text('subtitle','Destination','Destination'),n('curve','Curve height (%)',15,-40,40,1)]}
 ]);
 m.register({id:'sports',name:'Cricket & Sports'},[
 {number:49,id:'player-stats',name:'Player Stats',help:'Enter your player name and stats. All labels and values stay editable.',settings:[duration,accent,text('title','Player','Player name'),text('data','Label: value','Runs: 0\nBalls: 0\nStrike rate: 0',1000,true)]},
 {number:50,id:'scorecard',name:'Scorecard',help:'Use your own team names, score and overs. No live statistics are fetched.',settings:[duration,accent,text('title','Match','Team A vs Team B'),text('score','Score','0/0',40),text('subtitle','Overs / note','0 overs')]},
 {number:51,id:'player-compare',name:'Player Comparison',help:'Two player names with parallel stats. Enter one label: left value | right value per line.',settings:[duration,accent,text('title','Player one','Player A'),text('subtitle','Player two','Player B'),text('data','Comparison','Runs: 0 | 0\nAverage: 0 | 0\nStrike rate: 0 | 0',1000,true)]},
 {number:52,id:'lineup',name:'Team Lineup',help:'Enter one player per line, up to 11. Text and positions remain editable.',settings:[duration,accent,text('title','Team','Team name'),text('data','Players','Player 1\nPlayer 2\nPlayer 3',1200,true)]},
 {number:53,id:'points-table',name:'Points Table',help:'Comma-separated columns, one row per line. Include a header row; 2–6 columns and up to 12 rows.',settings:[duration,accent,text('title','Title','Points table'),text('data','Table','Team,Played,Won,Points\nTeam A,0,0,0\nTeam B,0,0,0',2400,true)]},
 {number:54,id:'sports-impact',name:'Four / Six / Wicket',help:'Editable impact lettering with a short overshoot and fade.',settings:[duration,accent,c('title','Event','SIX',['FOUR','SIX','WICKET']),text('subtitle','Subtitle','',160)]}
 ]);
 // Optional subtitle may be empty.
 m.find('sports-impact').settings[m.find('sports-impact').settings.length-1].allowEmpty=true;
 var ids=['lower-third','arrow','callout','highlight','progress','timer','chart','document-highlight','history-timeline','map-route','player-stats','scorecard','player-compare','lineup','points-table','sports-impact'];
 function rows(data,max){var r=String(data).replace(/^\s+|\s+$/g,'').split(/\r?\n/);if(!r.length||r.length>max)throw Error('Enter between 1 and '+max+' rows.');for(var i=0;i<r.length;i++)if(!r[i].replace(/\s/g,''))throw Error('Remove empty data rows.');return r;}
 function pair(row){var at=row.indexOf(':');if(at<1||!row.substring(at+1).replace(/\s/g,''))throw Error('Use Label: value on each line.');return [row.substring(0,at).replace(/^\s+|\s+$/g,''),row.substring(at+1).replace(/^\s+|\s+$/g,'')];}
 function make(id,settings,w,h){
  var p=m.validate({id:id,settings:settings||{}}),s=p.settings,items=[],unit=Math.min(w,h),font=unit*.045,white='#f4f4f4',accent=s.color||'#d9e56c',ink='#17191c',i,data;
  function label(name,value,x,y,size,maxWidth,color,role){items.push({type:'text',name:name,text:String(value),position:[x,y],fontSize:size,maxWidth:maxWidth,color:color||white,role:role||'label'});return items[items.length-1];}
  function rect(name,x,y,width,height,color,opacity,role){items.push({type:'rect',name:name,position:[x,y],size:[Math.max(.01,width),Math.max(.01,height)],color:color||accent,opacity:opacity===undefined?100:opacity,role:role||'decoration',radius:Math.min(12,height*.2)});return items[items.length-1];}
  function line(name,points,color,width,role){items.push({type:'path',name:name,position:[0,0],points:points,color:color||accent,stroke:width||unit*.006,role:role||'line',draw:true});return items[items.length-1];}
  function panel(title){rect('Panel',w*.5,h*.5,w*.86,Math.min(h*.75,unit*.85),ink);label('Heading',title,w*.5,h*.5-unit*.34,font*1.15,w*.76,accent,'heading');}
  if(id==='lower-third'){
   rect('Name plate',w*.45,h*.82,w*.76,unit*.18,ink);rect('Accent',w*.075,h*.82,unit*.012,unit*.18,accent);label('Name',s.title,w*.45,h*.80,font*1.15,w*.68,white,'name');label('Subtitle',s.subtitle,w*.45,h*.845,font*.65,w*.68,'#bdbdbd','subtitle');
  }else if(id==='arrow'){
   var a=s.angle*Math.PI/180,cx=w*.5,cy=h*.5,dx=Math.cos(a)*unit*.25,dy=Math.sin(a)*unit*.25,nx=-Math.sin(a)*unit*.055,ny=Math.cos(a)*unit*.055;
   line('Shaft',[[cx-dx,cy-dy],[cx+dx,cy+dy]]);line('Arrow head',[[cx+dx-dx*.2+nx,cy+dy-dy*.2+ny],[cx+dx,cy+dy],[cx+dx-dx*.2-nx,cy+dy-dy*.2-ny]]);
  }else if(id==='callout'){
   rect('Label background',w*.65,h*.4,w*.5,unit*.13,ink);label('Label',s.title,w*.65,h*.4,font*.7,w*.43);line('Leader',[[w*.25,h*.63],[w*.43,h*.46],[w*.5,h*.46]]);rect('Target',w*.25,h*.63,unit*.02,unit*.02,accent);
  }else if(id==='highlight'||id==='document-highlight'){
   var px=w*s.x/100,py=h*s.y/100;rect('Marker',px,py,w*s.width/100,h*(id==='highlight'?s.height:3)/100,accent,40,'highlight');
   if(id==='document-highlight')label('Annotation',s.title,px,py-unit*.06,font*.65,w*.8,accent);
  }else if(id==='progress'){
   rect('Track',w*.5,h*.5,w*.7,unit*.035,'#383b40');var bar=rect('Progress',w*.15+w*.7*s.value/200,h*.5,w*.7*s.value/100,unit*.035,accent,100,'progress');bar.grow=true;label('Value',s.value+'%',w*.5,h*.5-unit*.08,font,w*.6);
  }else if(id==='timer'){
   label('Label',s.title,w*.5,h*.45,font*.6,w*.8,'#bdbdbd');var timer=label('Counter',String(s.value),w*.5,h*.53,font*2,w*.8,white,'counter');timer.counter={start:s.value,direction:s.direction==='down'?-1:1};
  }else if(id==='chart'){
   data=rows(s.data,12);var parsed=[],maximum=0;for(i=0;i<data.length;i++){var entry=pair(data[i]),v=Number(entry[1]);if(!isFinite(v))throw Error('Chart values must be a number.');if(v<0)throw Error('Chart values must be nonnegative.');parsed.push([entry[0],v]);maximum=Math.max(maximum,v);}label('Title',s.title,w*.5,h*.2,font,w*.85,accent);
   var gap=Math.min(h*.5/data.length,unit*.11);for(i=0;i<parsed.length;i++){var yy=h*.3+i*gap,bw=w*.5*(maximum?parsed[i][1]/maximum:0);label('Label '+i,parsed[i][0],w*.17,yy,font*.55,w*.23);if(bw>0){var bar=rect('Bar '+i,w*.32+bw/2,yy,bw,gap*.45,accent,100,'bar');bar.grow=true;}label('Value '+i,parsed[i][1],w*.89,yy,font*.55,w*.12);}
  }else if(id==='history-timeline'){
   data=rows(s.data,8);label('Heading',s.title,w*.5,h*.16,font,w*.8,accent);line('Timeline',[[w*.25,h*.26],[w*.25,h*.82]],'#7b7b7b',unit*.003);var gap=h*.5/Math.max(1,data.length-1);for(i=0;i<data.length;i++){var entry=pair(data[i]),yy=h*.28+i*gap;rect('Event point '+i,w*.25,yy,unit*.015,unit*.015,accent);label('Year '+i,entry[0],w*.13,yy,font*.6,w*.19,accent);label('Event '+i,entry[1],w*.59,yy,font*.62,w*.6);}
  }else if(id==='map-route'){
   var route=line('Route',[[w*.2,h*.65],[w*.8,h*.35]],accent,unit*.006);route.outTangents=[[w*.25,-h*s.curve/100],[0,0]];route.inTangents=[[0,0],[-w*.25,h*s.curve/100]];
   rect('Start pin',w*.2,h*.65,unit*.018,unit*.018,accent);rect('Destination pin',w*.8,h*.35,unit*.018,unit*.018,accent);label('Start',s.title,w*.2,h*.65+unit*.07,font*.6,w*.32);label('Destination',s.subtitle,w*.8,h*.35-unit*.07,font*.6,w*.32);
  }else if(id==='player-stats'){
   panel(s.title);data=rows(s.data,6);for(i=0;i<data.length;i++){var entry=pair(data[i]),yy=h*.5-unit*.2+i*unit*.10;label('Stat label '+i,entry[0],w*.3,yy,font*.65,w*.3,'#bdbdbd','stat-label');label('Stat value '+i,entry[1],w*.69,yy,font*.85,w*.3,white,'stat-value');}
  }else if(id==='scorecard'){
   panel(s.title);label('Score',s.score,w*.5,h*.5,font*2.6,w*.74,white,'score');label('Overs',s.subtitle,w*.5,h*.5+unit*.18,font*.7,w*.75,accent,'overs');
  }else if(id==='player-compare'){
   rect('Panel',w*.5,h*.5,w*.9,unit*.8,ink);label('Player one',s.title,w*.25,h*.5-unit*.3,font*.8,w*.38,accent);label('Player two',s.subtitle,w*.75,h*.5-unit*.3,font*.8,w*.38,accent);data=rows(s.data,5);for(i=0;i<data.length;i++){var entry=pair(data[i]),values=entry[1].split('|');if(values.length!==2)throw Error('Use Label: left value | right value for comparison rows.');var yy=h*.5-unit*.15+i*unit*.1;label('Metric '+i,entry[0],w*.5,yy,font*.45,w*.25,'#bdbdbd');label('Left '+i,values[0].replace(/^\s+|\s+$/g,''),w*.22,yy,font*.8,w*.25);label('Right '+i,values[1].replace(/^\s+|\s+$/g,''),w*.78,yy,font*.8,w*.25);}
  }else if(id==='lineup'){
   data=rows(s.data,11);label('Team',s.title,w*.5,h*.16,font,w*.8,accent);for(i=0;i<data.length;i++){var col=i%2,row=Math.floor(i/2),xx=w*(col?.72:.28),yy=h*.29+row*Math.min(h*.10,unit*.12);rect('Plate '+i,xx,yy,w*.39,unit*.09,ink);label('Player '+i,(i+1)+'. '+data[i],xx,yy,font*.57,w*.35);}
  }else if(id==='points-table'){
   data=rows(s.data,13);var table=[],columns=0;for(i=0;i<data.length;i++){var cells=data[i].split(',');if(i===0){columns=cells.length;if(columns<2||columns>6)throw Error('Use 2 to 6 table columns.');}if(cells.length!==columns)throw Error('Every table row needs the same number of columns.');table.push(cells);}if(table.length<2)throw Error('Add a header and at least one table row.');label('Heading',s.title,w*.5,h*.17,font,w*.85,accent);var gap=Math.min(h*.55/table.length,unit*.085);for(i=0;i<table.length;i++){var yy=h*.28+i*gap;rect('Row '+i,w*.5,yy,w*.9,gap*.9,i===0?'#373b29':ink);for(var j=0;j<columns;j++)label('Cell '+i+' '+j,table[i][j].replace(/^\s+|\s+$/g,''),w*.05+w*.9*(j+.5)/columns,yy,font*.45,w*.84/columns,i===0?accent:white);}
  }else if(id==='sports-impact'){
   var impact=label('Event',s.title,w*.5,h*.48,font*3.8,w*.9,accent,'impact');impact.pop=true;if(s.subtitle)label('Subtitle',s.subtitle,w*.5,h*.48+unit*.16,font*.75,w*.8);
  }else throw Error('Choose a graphics builder.');
  return {id:id,name:m.find(id).name,width:w,height:h,duration:s.duration||5,layers:items};
 }
 var api={make:make,ids:ids};root.SLToolkitBuilderModel=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof $!=='undefined'&&$.global?$.global:this);
