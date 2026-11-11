'use strict';
/* Count DEFLATE output before native allocation. This protects older CEP Node
   versions even when they do not enforce inflateSync's maxOutputLength option.
   RFC 1951 output sizes are checked without materializing the pixel history. */
const zlib=require('zlib'),BufferType=require('buffer').Buffer;
const MAX_RAW=64*1024*1024;
const lengthBase=[3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258];
const lengthExtra=[0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0];
const distanceBase=[1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577];
const distanceExtra=[0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13];
function tree(lengths){const count=new Array(16).fill(0),next=new Array(16).fill(0),tables=[];let maximum=0,code=0;
 for(const n of lengths){if(n<0||n>15)throw Error('Invalid code length');if(n){count[n]++;maximum=Math.max(maximum,n);}}
 for(let n=1;n<=15;n++){code=(code+count[n-1])*2;if(code+count[n]>Math.pow(2,n))throw Error('Oversubscribed code tree');next[n]=code;tables[n]=[];}
 for(let symbol=0;symbol<lengths.length;symbol++){const n=lengths[symbol];if(!n)continue;let value=next[n]++,reverse=0;for(let k=0;k<n;k++){reverse=(reverse<<1)|(value&1);value>>>=1;}tables[n][reverse]=symbol;}
 return {tables,maximum};
}
const fixedLengths=[];for(let i=0;i<288;i++)fixedLengths[i]=i<144?8:i<256?9:i<280?7:8;
const fixedLiteral=tree(fixedLengths),fixedDistance=tree(new Array(32).fill(5));
function counted(data,expected){
 if(data.length<6||(data[0]&15)!==8||(data[0]>>>4)>7||((data[0]<<8)|data[1])%31||(data[1]&32))throw Error('Invalid PNG zlib header');
 let pos=2,bits=0,hold=0,produced=0,final=0,blocks=0;const limit=data.length-4,window=Math.pow(2,(data[0]>>>4)+8);
 function take(n){while(bits<n){if(pos>=limit)throw Error('Truncated deflate stream');hold|=data[pos++]<<bits;bits+=8;}const result=hold&((1<<n)-1);hold>>>=n;bits-=n;return result;}
 function symbol(t){let value=0;for(let n=1;n<=t.maximum;n++){value|=take(1)<<(n-1);const found=t.tables[n][value];if(found!==undefined)return found;}throw Error('Invalid deflate code');}
 function add(n){produced+=n;if(produced>expected)throw Error('Pixel stream exceeds image dimensions');}
 while(!final){if(++blocks>10000)throw Error('Too many deflate blocks');final=take(1);const kind=take(2);if(kind===3)throw Error('Reserved deflate block');
  if(kind===0){hold=0;bits=0;const n=take(16),complement=take(16);if((n^0xffff)!==complement||pos+n>limit)throw Error('Invalid stored block');pos+=n;add(n);continue;}
  let literals=fixedLiteral,distances=fixedDistance;
  if(kind===2){const literalCount=take(5)+257,distanceCount=take(5)+1,codeCount=take(4)+4;if(literalCount>286)throw Error('Invalid literal alphabet');const order=[16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15],codeLengths=new Array(19).fill(0);for(let i=0;i<codeCount;i++)codeLengths[order[i]]=take(3);const codes=tree(codeLengths),lengths=[],total=literalCount+distanceCount;
   while(lengths.length<total){const n=symbol(codes);if(n<=15)lengths.push(n);else{let repeat,value=0;if(n===16){if(!lengths.length)throw Error('Missing repeated code length');repeat=take(2)+3;value=lengths[lengths.length-1];}else if(n===17)repeat=take(3)+3;else if(n===18)repeat=take(7)+11;else throw Error('Invalid repeated code length');if(lengths.length+repeat>total)throw Error('Too many code lengths');while(repeat--)lengths.push(value);}}
   if(!lengths[256])throw Error('Missing end-of-block code');literals=tree(lengths.slice(0,literalCount));distances=tree(lengths.slice(literalCount));
  }
  while(true){const n=symbol(literals);if(n<256){add(1);continue;}if(n===256)break;if(n<257||n>285)throw Error('Invalid length symbol');const index=n-257,length=lengthBase[index]+take(lengthExtra[index]),distanceCode=symbol(distances);if(distanceCode>29)throw Error('Invalid distance symbol');const distance=distanceBase[distanceCode]+take(distanceExtra[distanceCode]);if(distance>produced||distance>window)throw Error('Invalid backward distance');add(length);}
 }
 if(pos!==limit||produced!==expected)throw Error('Pixel stream length differs from image dimensions');return produced;
}
function layout(width,height,color,depth,interlace){const channels={0:1,2:3,3:1,4:2,6:4}[color],passes=interlace?[[0,0,8,8],[4,0,8,8],[0,4,4,8],[2,0,4,4],[0,2,2,4],[1,0,2,2],[0,1,1,2]]:[[0,0,1,1]],rows=[];let expected=0;
 for(const pass of passes){const w=Math.max(0,Math.ceil((width-pass[0])/pass[2])),h=Math.max(0,Math.ceil((height-pass[1])/pass[3]));if(!w||!h)continue;const stride=1+Math.ceil(w*channels*depth/8);expected+=stride*h;rows.push({stride,count:h});}
 if(!expected||expected>MAX_RAW)throw Error('Preview pixel size exceeds safe limit');return {expected,rows};
}
function validate(bytes,ranges,width,height,color,depth,interlace){try{
 const shape=layout(width,height,color,depth,interlace),size=ranges.reduce((sum,r)=>sum+r.size,0),compressed=BufferType.alloc(size);let at=0;
 for(const range of ranges)for(let i=0;i<range.size;i++)compressed[at++]=bytes[range.start+i];
 counted(compressed,shape.expected);
 const raw=zlib.inflateSync(compressed,{maxOutputLength:shape.expected});if(raw.length!==shape.expected)return false;
 at=0;for(const group of shape.rows)for(let r=0;r<group.count;r++){if(raw[at]>4)return false;at+=group.stride;}
 return at===raw.length;
 }catch(_){return false;}}
module.exports={validate,counted,layout,MAX_RAW};
