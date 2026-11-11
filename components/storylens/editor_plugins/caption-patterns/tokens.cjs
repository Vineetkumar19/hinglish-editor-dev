// Formatting-only tokens belong to a neighbouring word, not to another speech onset.
module.exports=function captionTokens(script){const words=[],prefix=[];for(const token of String(script).trim().split(/\s+/)){if(/[\p{L}\p{N}]/u.test(token)){words.push(prefix.concat(token).join(' '));prefix.length=0;}else if(words.length)words[words.length-1]+=' '+token;else prefix.push(token);}return words;};
