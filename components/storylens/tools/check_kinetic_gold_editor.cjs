// Execute the actual editor script to check changed-count timing and controls.
// Canvas metrics are stubs: this checks behavior, not browser visual fidelity.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const cfg=JSON.parse(fs.readFileSync('hinglish_captions/kinetic_gold_reference.json','utf8'));
const code=fs.readFileSync('hinglish_captions/kinetic_gold.js','utf8');
let checks=0;
for(let slot=0;slot<cfg.recipes.length;slot++)for(const count of [0,1,3,4,6,11,14]){
 const words=Array.from({length:count},(_,i)=>`word${i}`),drawn=[];
 const pen={font:'700 10px Arial',measureText(text){const size=Number(this.font.match(/([\d.]+)px/)[1]);return {width:text.length*size*.55,actualBoundingBoxLeft:0,actualBoundingBoxRight:text.length*size*.55,actualBoundingBoxAscent:size*.72,actualBoundingBoxDescent:size*.18}},save(){},restore(){},translate(){},scale(){},fillText(text){drawn.push(text)},strokeText(text){drawn.push(text)},beginPath(){},rect(){},clip(){},moveTo(){},lineTo(){},closePath(){},fill(){}};
 const canvas={style:{},getContext(){return pen},setAttribute(key,value){this[key]=value}};
 const caption={style:{},replaceChildren(...children){this.children=children}};
 const controls={'#font':{value:'template'},'#size':{value:'175'},'#position':{value:'73'}};
 const q={start:0,end:7,template_source:cfg.recipes[slot].text,template_slot:slot,words:[{text:'old',start:0,end:3.5},{text:'words',start:3.5,end:7}]};
 const parent={transform:'translate(37px, 19px) scale(1.75)'};
 const context={project:{kinetic_gold_profile:cfg},draw(){},document:{createElement(){return canvas},fonts:{load(){return Promise.resolve()}}},cues:[q],video:{currentTime:6.99,addEventListener(){}},wordsAt(){return words},currentStyle:'kinetic_gold_draft',visibility:'phrase',stage:{clientWidth:414,clientHeight:736},caption,captionPositionLayer:{style:parent},wordColors:[[]],templates:{kinetic_gold_draft:{default_position:.65}},fonts:{},$(key){return controls[key]},$$(){return []},updateSelection(){}};
 vm.createContext(context);vm.runInContext(code,context);vm.runInContext('draw()',context);
 if(count){
  const expected=count<=11?words:words.slice(11);
  assert.equal(canvas['aria-label'],expected.join(' '),`Lost edited words in pattern ${slot}, count ${count}`);
  for(const word of expected)assert(drawn.includes(word),`Never drew ${word}`);
  assert.equal(caption.style.top,'65%');
 }else assert.equal(caption.children.length,0);
 assert.equal(parent.transform,'translate(37px, 19px) scale(1.75)');
 checks++;
}
const result={checks,passed:true,scope:'Actual kinetic_gold.js execution with stub canvas metrics; not a browser or Storylens visual check'};
fs.writeFileSync('output/captions/kinetic-gold-reference-rebuild/editor-check.json',JSON.stringify(result,null,2));
console.log(JSON.stringify(result));
