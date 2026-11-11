const zlib=require('node:zlib');
function crc(bytes){let n=0xffffffff;for(const byte of bytes){n^=byte;for(let k=0;k<8;k++)n=n&1?(n>>>1)^0xedb88320:n>>>1;}return (n^0xffffffff)>>>0;}
function chunk(name,data){const type=Buffer.from(name),out=Buffer.alloc(data.length+12);out.writeUInt32BE(data.length);type.copy(out,4);data.copy(out,8);out.writeUInt32BE(crc(Buffer.concat([type,data])),data.length+8);return out;}
function png(){const header=Buffer.alloc(13);header.writeUInt32BE(1);header.writeUInt32BE(1,4);header[8]=8;header[9]=6;return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',header),chunk('IDAT',zlib.deflateSync(Buffer.from([0,255,255,255,255]))),chunk('IEND',Buffer.alloc(0))]);}
const passes=[[0,0,8,8],[4,0,8,8],[0,4,4,8],[2,0,4,4],[0,2,2,4],[1,0,2,2],[0,1,1,2]];
function imagePNG({width=9,height=9,depth=8,color=6,interlace=0,raw,compressed,options={}}={}){
 const channels={0:1,2:3,3:1,4:2,6:4}[color],header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=depth;header[9]=color;header[12]=interlace;
 if(!raw){const rows=[];for(const [x,y,dx,dy] of interlace?passes:[[0,0,1,1]]){const w=Math.max(0,Math.ceil((width-x)/dx)),h=Math.max(0,Math.ceil((height-y)/dy));if(!w||!h)continue;for(let r=0;r<h;r++)rows.push(Buffer.alloc(1+Math.ceil(w*channels*depth/8)));}raw=Buffer.concat(rows);}
 return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',header),...(color===3?[chunk('PLTE',Buffer.from([0,0,0,255,255,255]))]:[]),chunk('IDAT',compressed||zlib.deflateSync(raw,options)),chunk('IEND',Buffer.alloc(0))]);
}
module.exports={png,imagePNG};
