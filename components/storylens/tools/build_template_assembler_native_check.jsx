(function(){
 var out=new File('D:/Full Drive/remove silence/output/template-assembler-evidence/native-ae-build.json');
 function write(v){out.encoding='UTF-8';out.open('w');out.write(SLTA.json(v));out.close();}
 try{
  $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/template-assembler/host.jsx'));
  var rows=SLTA.ui.rows();
  for(var i=0;i<rows.length;i++)if(!rows[i].comp){var found=[];for(var j=0;j<rows[i].comps.length;j++)if(rows[i].comps[j].name==='Slideshow')found.push(rows[i].comps[j]);if(found.length!==1)throw new Error('The manual Slideshow choice is ambiguous.');rows[i].comp=found[0];}
  SLTA.ui.repeat.value=true;SLTA.ui.target.text='10:00';SLTA.ui.name.text='Storylens — 10 minute template check';
  var result=SLTA.ui.build();if(!result)throw new Error('The visible Build action did not complete.');
  result.originalProject=app.project.file?app.project.file.fsName:null;write(result);
  SLTA.ui.window.hide();
 }catch(e){write({error:true,details:String(e)});}
})();
