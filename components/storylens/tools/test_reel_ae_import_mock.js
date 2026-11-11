// A host-shape check for the saved Reel Recreate manifest. Native AE validation is separate.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'output/reel-recreate/dfb55ed4995b4f80bc58766a2b9bf6db/reel-plan.json'), 'utf8'));
let nextId = 1;
let textLayers = 0;
let failOnTextLayer = 0;
const all = [];
class FolderItem { constructor(name) { this.name = name; this.id = nextId++; this.parentFolder = null; } get items() { return collection(all.filter(x => x.parentFolder === this)); } remove() { all.splice(all.indexOf(this), 1); } }
class CompItem { constructor(name, width, height, duration, fps) { this.name = name; this.id = nextId++; this.width = width; this.height = height; this.duration = duration; this.frameRate = fps; this.comment = ''; this.layers = layers(); this.markerProperty = {setValueAtTime(){}}; } openInViewer() {} remove() { all.splice(all.indexOf(this), 1); } }
class FootageItem { constructor(file) { this.file = file; this.id = nextId++; this.name = file.fsName; this.duration = manifest.duration; } remove() { all.splice(all.indexOf(this), 1); } }
class File { constructor(value) { this.fsName = String(value); this.exists = fs.existsSync(this.fsName); } }
class ImportOptions { constructor(file) { this.file = file; } }
class MarkerValue { constructor(value) { this.value = value; } }
function collection(items) { const result = {length:items.length, addFolder(name){const x=new FolderItem(name);all.push(x);return x;}, addComp(name,w,h,p,d,f){const x=new CompItem(name,w,h,d,f);all.push(x);return x;}}; items.forEach((x,i)=>result[i+1]=x); return result; }
function valueProperty() { return {setValue(){}, setValueAtTime(){}, value:{fontSize:0}}; }
function layers() { const result=[]; result.add = source => layer(source); result.addSolid = () => layer(); result.addText = () => {textLayers++; if(textLayers===failOnTextLayer) throw Error('Injected text failure'); return layer(null,true);}; return result; }
function layer(source,isText) { const result = {source, name:'', enabled:true, audioEnabled:false, sourceRectAtTime(){return {left:0,top:0,width:100,height:40};}, property(name) { if(name==='ADBE Text Properties') return {property(){return {get value(){return {fontSize:0};}, setValue(doc){assert(Number.isInteger(doc.tracking),'tracking must be an integer');}};}}; if(name==='ADBE Marker')return {setValueAtTime(){}}; if(name==='ADBE Transform Group')return {property(){return valueProperty();}}; return valueProperty(); }}; return result; }
const rootFolder = new FolderItem('Root');
const project = {rootFolder, get numItems(){return all.length;}, get items(){return collection(all);}, item(i){return all[i-1];}, importFile(options){const item=new FootageItem(options.file);all.push(item);return item;}};
const app = {project, beginUndoGroup(){},endUndoGroup(){}};
const context = {app,File,ImportOptions,FolderItem,CompItem,FootageItem,MarkerValue,ParagraphJustification:{LEFT_JUSTIFY:0},hJSON:JSON.stringify,console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root,'editor_plugins/shared/aftereffects-panel.jsx'),'utf8'),context);
const first = JSON.parse(context.storylensPanelImport(manifest));
assert(first.ok, JSON.stringify(first));
assert.strictEqual(textLayers,manifest.caption.words.length);
assert.strictEqual(all.filter(x=>x instanceof CompItem).length,1+manifest.sections.length+new Set(manifest.caption.words.map(x=>x.cue)).size);
const count = all.length;
const second = JSON.parse(context.storylensPanelImport(manifest));
assert(second.already_present);
assert.strictEqual(all.length,count);
const revisionOne = {...manifest,revision_id:'a'.repeat(32),revision_number:1,caption:{...manifest.caption,style:'caption_3'}};
const firstUpdate = JSON.parse(context.storylensPanelImport(revisionOne));
assert(firstUpdate.ok&&!firstUpdate.already_present,JSON.stringify(firstUpdate));
const revisionTwo = {...manifest,revision_id:'b'.repeat(32),revision_number:2,caption:{...manifest.caption,style:'caption_4'}};
const secondUpdate = JSON.parse(context.storylensPanelImport(revisionTwo));
assert(secondUpdate.ok&&!secondUpdate.already_present,JSON.stringify(secondUpdate));
assert.strictEqual(all.filter(x=>x instanceof CompItem&&x.comment.startsWith('StorylensReel:')).length,3);
const duplicateUpdate = JSON.parse(context.storylensPanelImport(revisionTwo));
assert(duplicateUpdate.already_present);
const beforeFailure = all.length;
const broken = {...manifest,id:'failure-check'};
failOnTextLayer = textLayers+4;
const third = JSON.parse(context.storylensPanelImport(broken));
assert(/Injected text failure/.test(third.error),JSON.stringify(third));
assert.strictEqual(all.length,beforeFailure,'a failed import left new project items behind');
console.log(JSON.stringify({status:'pass',captionWordsPerVersion:manifest.caption.words.length,mediaSlotsPerVersion:manifest.sections.length,captionGroupsPerVersion:new Set(manifest.caption.words.map(x=>x.cue)).size,beatsPerVersion:manifest.beats.length,compositions:3,revisionIsolation:true,idempotentPerRevision:true,failedImportCleanup:true}));
