/* Shared ES3 recipe/timing model. Native JSX and the panel use the same recipe IDs. */
(function(root){
 var recipes=[
  {id:'text-fade',kind:'text',name:'Fade In',motion:'fade'},
  {id:'text-typewriter',kind:'text',name:'Typewriter',motion:'typewriter'},
  {id:'text-left',kind:'text',name:'Slide Left',motion:'left'},
  {id:'text-right',kind:'text',name:'Slide Right',motion:'right'},
  {id:'text-up',kind:'text',name:'Slide Up',motion:'up'},
  {id:'text-down',kind:'text',name:'Slide Down',motion:'down'},
  {id:'text-random',kind:'text',name:'Random Words',motion:'random'},
  {id:'text-words',kind:'text',name:'Word Rise',motion:'words'},
  {id:'text-pop',kind:'text',name:'Pop In',motion:'pop'},
  {id:'text-blur',kind:'text',name:'Blur In',motion:'blur'},
  {id:'element-right',kind:'element',name:'Left to Right',motion:'right'},
  {id:'element-left',kind:'element',name:'Right to Left',motion:'left'},
  {id:'element-up',kind:'element',name:'Bottom to Top',motion:'up'},
  {id:'element-down',kind:'element',name:'Top to Bottom',motion:'down'},
  {id:'element-fade',kind:'element',name:'Fade In',motion:'fade'},
  {id:'element-out',kind:'element',name:'Fade Out',motion:'out'},
  {id:'element-zoom-in',kind:'element',name:'Zoom In',motion:'zoom-in'},
  {id:'element-zoom-out',kind:'element',name:'Zoom Out',motion:'zoom-out'}
 ];
 function find(id){for(var i=0;i<recipes.length;i++)if(recipes[i].id===id)return recipes[i];throw Error('Choose a motion preset from Effects.');}
 function validate(p){var r=find(p.id);if(typeof p.duration!=='number'||!isFinite(p.duration)||p.duration<.1||p.duration>10)throw Error('Choose an animation duration from 0.1 to 10 seconds.');if(p.blur!==undefined&&typeof p.blur!=='boolean'||p.exit!==undefined&&typeof p.exit!=='boolean')throw Error('Choose the blur and fade-out options again.');if(p.text_scope!==undefined&&p.text_scope!=='word'&&p.text_scope!=='words')throw Error('Choose Word or Words mode.');return {id:r.id,duration:p.duration,blur:p.blur!==false,exit:p.exit!==false,kind:r.kind,text_scope:p.text_scope||'words'};}
 function plan(p,start,out,frame){p=validate(p);var r=find(p.id),end=start+p.duration,exitEnd=out-frame,exitStart=exitEnd-Math.min(.5,p.duration/2),hasExit=p.exit&&r.motion!=='out';if(!isFinite(start)||!isFinite(out)||!isFinite(frame)||frame<=0||start<0||end>exitEnd||(hasExit&&end+frame>exitStart))throw Error('This layer is too short for that duration. Move the playhead earlier, shorten the animation, or turn off Fade out.');return {recipe:r,start:start,end:end,exitStart:exitStart,exitEnd:exitEnd,exit:hasExit,blur:p.blur,duration:p.duration};}
 function order(n,seed){var a=[],i,j,t,s=seed||37;for(i=0;i<n;i++)a.push(i);for(i=n-1;i>0;i--){s=s*16807%2147483647;j=s%(i+1);t=a[i];a[i]=a[j];a[j]=t;}var same=true;for(i=0;i<n;i++)if(a[i]!==i)same=false;if(same&&n>1){t=a[0];a[0]=a[n-1];a[n-1]=t;}return a;}
 // ExtendScript's installed adapter has hJSON, not browser JSON. Keep the model
 // self-contained for selectors, success replies and failures before any edit.
 function quote(value){return '"'+String(value).replace(/[\\"\u0000-\u001f\u2028\u2029]/g,function(c){if(c==='"')return '\\"';if(c==='\\')return '\\\\';var hex=c.charCodeAt(0).toString(16);while(hex.length<4)hex='0'+hex;return '\\u'+hex;})+'"';}
 function stringify(value){var t=typeof value,a=[],i;if(value===null||t==='undefined')return 'null';if(t==='string')return quote(value);if(t==='number')return isFinite(value)?String(value):'null';if(t==='boolean')return String(value);if(Object.prototype.toString.call(value)==='[object Array]'){for(i=0;i<value.length;i++)a.push(stringify(value[i]));return '['+a.join(',')+']';}for(i in value)if(Object.prototype.hasOwnProperty.call(value,i)&&typeof value[i]!=='undefined')a.push(quote(i)+':'+stringify(value[i]));return '{'+a.join(',')+'}';}
 function selector(r,control,seed){var code='var p=Math.max(0,Math.min(100,effect('+quote(control)+')(1)));';if(r.motion==='typewriter')return code+'p/100*textTotal>=textIndex?0:100;';if(r.motion!=='words'&&r.motion!=='random')return code+'100-p;';code+='var n=Math.max(1,textTotal),rank=textIndex-1;';if(r.motion==='random')code+='var a=('+order.toString()+')(n,'+(seed||37)+');rank=a[textIndex-1];';return code+'var width=Math.max(1,n*.45);ease(p/100*(n-1+width)-rank,0,width,100,0);';}
 var api={catalog:function(){return recipes.slice(0);},find:find,validate:validate,plan:plan,order:order,selector:selector,quote:quote,stringify:stringify};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SLQuickMotionModel=api;
})(typeof $!=='undefined'&&$.global?$.global:this);
