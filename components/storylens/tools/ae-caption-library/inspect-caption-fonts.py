from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from hinglish_app.broll_ae_direct import AfterEffectsDirect
result=AfterEffectsDirect(root,None)._call('''
var result=[],names=['Inter-Bold','Inter-Medium','Inter-Regular','StorylensCaptionOne-Bold','StorylensCaptionOne-Medium'];
for(var i=0;i<names.length;i++){var found=app.fonts.getFontsByPostScriptName(names[i]),fonts=[];
for(var j=0;j<found.length;j++)fonts.push({name:found[j].postScriptName,family:found[j].familyName,style:found[j].styleName,substitute:found[j].isSubstitute});result.push({requested:names[i],found:fonts});}
return {fonts:result};
''')
(root/'output/caption-one-general-speech-20261029/native-fonts.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
