'use strict';
/* CEP-compatible PNG container validation. Do not use Buffer.subarray().toString:
   older CEP Node builds can return a plain Uint8Array for subarray. */
const fs=require('fs'),path=require('path'),NativeBuffer=require('buffer').Buffer,pixels=require('./png-pixels.cjs');
const MAX_BYTES=5*1024*1024,magic=[137,80,78,71,13,10,26,10],table=[];
for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=c&1?(c>>>1)^0xedb88320:c>>>1;table[n]=c>>>0;}
function uint(b,p){return (b[p]*16777216+b[p+1]*65536+b[p+2]*256+b[p+3])>>>0;}
function crc(b,start,end){let c=0xffffffff;for(let i=start;i<end;i++)c=table[(c^b[i])&255]^(c>>>8);return (c^0xffffffff)>>>0;}
function valid(b){
 if(!b||b.length<57||b.length>MAX_BYTES||magic.some((v,i)=>b[i]!==v))return false;
 let at=8,ihdr=false,idat=false,end=false,palette=false,color,depth,width,height,interlace,parts=0;const ranges=[];
 while(at<b.length){if(++parts>10000||at+12>b.length)return false;const size=uint(b,at),stop=at+12+size;if(stop>b.length)return false;
  const type=String.fromCharCode(b[at+4],b[at+5],b[at+6],b[at+7]);if(!/^[A-Za-z]{4}$/.test(type)||crc(b,at+4,at+8+size)!==uint(b,at+8+size))return false;
  if(!ihdr&&type!=='IHDR')return false;
  if(type==='IHDR'){if(ihdr||size!==13)return false;ihdr=true;width=uint(b,at+8);height=uint(b,at+12);depth=b[at+16];color=b[at+17];interlace=b[at+20];const allowed={0:[1,2,4,8,16],2:[8,16],3:[1,2,4,8],4:[8,16],6:[8,16]};if(!width||!height||width>4096||height>4096||width*height>16777216||!allowed[color]||allowed[color].indexOf(depth)<0||b[at+18]!==0||b[at+19]!==0||interlace>1)return false;}
  else if(type==='PLTE'){if(idat||!size||size%3||size>768)return false;palette=true;}
  else if(type==='IDAT'){if(color===3&&!palette)return false;if(size)idat=true;ranges.push({start:at+8,size});}
  else if(type==='IEND'){if(size||!idat||stop!==b.length)return false;end=true;}
  else if(type[0]===type[0].toUpperCase())return false; // Unknown critical chunk.
  at=stop;
 }
 return ihdr&&idat&&end&&pixels.validate(b,ranges,width,height,color,depth,interlace);
}
function diagnose(file){const report={reader_version:'png-reader-20261027-pixels-2',module_path:__filename,file:String(file),runtime:{},chunks:[]};try{report.runtime=require('process').versions||{};}catch(_){}
 try{report.exists=fs.existsSync(file);if(!report.exists)return report;const s=fs.lstatSync(file);report.stat={size:s.size,mtime_ms:s.mtimeMs,mtime:String(s.mtime),file:s.isFile(),symlink:s.isSymbolicLink()};if(!s.isFile()||s.isSymbolicLink()||s.size>MAX_BYTES)return report;
  const b=fs.readFileSync(file);report.byte_type=Object.prototype.toString.call(b);report.constructor=b.constructor&&b.constructor.name;report.length=b.length;report.signature=[];for(let i=0;i<Math.min(8,b.length);i++)report.signature.push(b[i]);report.valid=valid(b);
  for(let at=8,n=0;at+12<=b.length&&n<6;n++){const size=uint(b,at),stop=at+12+size,type=String.fromCharCode(b[at+4],b[at+5],b[at+6],b[at+7]);const row={type,size,within_file:stop<=b.length};if(stop>b.length){report.chunks.push(row);break;}row.stored_crc=uint(b,at+8+size);row.calculated_crc=crc(b,at+4,at+8+size);report.chunks.push(row);at=stop;}
  if(report.valid){try{const encoded=NativeBuffer.prototype.toString.call(b,'base64');report.encoding_ok=true;report.encoded_length=encoded.length;report.encoded_prefix=encoded.slice(0,12);}catch(e){report.encoding_ok=false;report.encoding_error=String(e.stack||e);}}
 }catch(e){report.exception=String(e.stack||e);}return report;
}
const logged=new Map();
function recordFailure(file,stage,error){try{const relative=path.relative(path.resolve(__dirname,'../../cache'),path.resolve(file));if(path.isAbsolute(relative)||relative.startsWith('..')||!/^cinematic-text(?:-gallery)?[\\/]/i.test(relative))return;const stamp=fs.existsSync(file)?String(fs.statSync(file).mtime):'missing',key=String(file)+'|'+stage+'|'+stamp;if(logged.has(key))return;logged.set(key,true);if(logged.size>500)logged.clear();const folder=path.resolve(__dirname,'../../cache/editor-panel');if(!fs.existsSync(folder))fs.mkdirSync(folder,{recursive:true});const output=path.join(folder,'cinematic-preview-reader-diagnostic.json');if(fs.existsSync(output)&&fs.lstatSync(output).isSymbolicLink())return;let entries=[];try{const previous=JSON.parse(fs.readFileSync(output,'utf8'));entries=Array.isArray(previous.entries)?previous.entries.slice(-7):[];}catch(_){}const entry=diagnose(file);entry.stage=stage;entry.time=new Date().toISOString();if(error)entry.caught_exception=String(error.stack||error);entries.push(entry);fs.writeFileSync(output,JSON.stringify({entries},null,2));}catch(_){} }
function read(file){try{if(!fs.existsSync(file)){recordFailure(file,'missing');return null;}const s=fs.lstatSync(file);if(s.isSymbolicLink()||!s.isFile()||s.size>MAX_BYTES||s.size<57){recordFailure(file,'file-guard');return null;}const bytes=fs.readFileSync(file);if(!valid(bytes)){recordFailure(file,'container-invalid');return null;}return 'data:image/png;base64,'+NativeBuffer.prototype.toString.call(bytes,'base64');}catch(e){recordFailure(file,'read-or-encode-exception',e);throw e;}}
function image(file){const result=read(file);if(!result)throw Error('The preview file is incomplete or unreadable. Press Preview to rebuild it.');return result;}
module.exports={valid,read,image,diagnose};
