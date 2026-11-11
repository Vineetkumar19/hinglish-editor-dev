"""Display spoken quantities as digits without translating or retiming speech."""
from dataclasses import replace
import re
import unicodedata

SMALL={word:i for i,word in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split())}
SMALL.update(dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10))))
HINDI='ek do teen chaar paanch chhe saat aath nau das gyarah barah terah chaudah pandrah solah satrah atharah unnis bees ikkis bais teis chaubis pachis chhabbis sattais atthais untis tees ikattis battis taintis chauntis paintis chhattis saintis adtis untalis chalis iktalis bayalis taintalis chawalis paintalis chhiyalis saintalis adtalis unchas pachas ikyavan bavan tirpan chauvan pachpan chhappan sattavan atthavan unsath saath iksath basath tirsath chaunsath painsath chhiyasath sadsath adsath unhattar sattar ikhattar bahattar tihattar chauhattar pachhattar chhihattar satahattar athhattar unasi assi ikyasi bayasi tirasi chaurasi pachasi chhiyasi sattasi atthasi navasi nabbe ikyanve banve tiranve chauranve panchanve chhiyanve sattanve atthanve ninyanve'.split()
SMALL.update({word:i for i,word in enumerate(HINDI,1)})
SMALL.update({'shunya':0,'char':4,'panch':5,'chhah':6,'gyaarah':11,'baarah':12,'chauda':14,
              'pandra':15,'sola':16,'satra':17,'athara':18,'atharah':18,'unnees':19,
              'baais':22,'chaubees':24,'pachees':25,'pachchees':25,'chabbis':26,
              'chaalees':40,'pachaas':50,'sattar':70,'nabbe':90})
SMALL.update(dict(zip('शून्य एक दो तीन चार पांच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस'.split(),range(31))))
SMALL.update(dict(zip('इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्नासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे'.split(),range(31,100))))
ORDINAL={word:i for i,word in enumerate('first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth'.split(),1)}
ORDINAL.update(dict(zip('twentieth thirtieth fortieth fiftieth sixtieth seventieth eightieth ninetieth'.split(),range(20,100,10))))


def ordinal(value):
    return str(value)+('th' if value%100 in (11,12,13) else {1:'st',2:'nd',3:'rd'}.get(value%10,'th'))
SCALE={'hundred':100,'sau':100,'सौ':100,'thousand':1000,'hazar':1000,'hazaar':1000,'hajaar':1000,'हजार':1000,'हज़ार':1000,
       'lakh':100000,'lac':100000,'लाख':100000,'million':1000000,'crore':10000000,'करोड़':10000000,'billion':1000000000}
UNITS=set('saal sal saalon varsh years year old age runs run score wickets wicket balls ball overs over percent percentage rupees rupee lakh crore matches match titles title baar din days day minute minutes seconds second साल वर्ष रन विकेट'.split())


def key(text):
    text=unicodedata.normalize('NFC',text)
    text=''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c)) if not re.search(r'[\u0900-\u097f]',text) else text
    return text.strip('.,!?;:()[]{}\"\'').casefold()


def digits(words):
    """Merge a spoken number's timed words; keep ambiguous Hindi verbs untouched."""
    expanded=[]
    for word in words:
        # Devanagari/other decimal glyphs denote the same values as ASCII digits.
        word=replace(word,text=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in word.text))
        parts=word.text.split('-')
        if len(parts)>1 and all(key(p) in SMALL for p in parts[:-1]) and (key(parts[-1]) in SMALL or key(parts[-1]) in ORDINAL):
            expanded.extend(replace(word,text=p) for p in parts)
        else:expanded.append(word)
    words=expanded
    output=[];i=0
    while i<len(words):
        first=key(words[i].text)
        if first=='second' and i and (key(words[i-1].text) in SMALL or key(words[i-1].text).isdigit() or key(words[i-1].text) in {'last','per','a','every'}):
            output.append(words[i]);i+=1;continue
        if first in ORDINAL:
            output.append(replace(words[i],text=re.sub(re.escape(first),ordinal(ORDINAL[first]),words[i].text,flags=re.I)))
            i+=1;continue
        if first in SMALL and SMALL[first]>=20 and SMALL[first]%10==0 and i+1<len(words) and key(words[i+1].text) in ORDINAL and ORDINAL[key(words[i+1].text)]<10 and words[i+1].start-words[i].end<=.45:
            tail=re.search(r'''[.,!?;:)\]}"'”’।]*$''',words[i+1].text)[0]
            output.append(replace(words[i],text=ordinal(SMALL[first]+ORDINAL[key(words[i+1].text)])+tail,end=words[i+1].end))
            i+=2;continue
        if first not in SMALL and first not in SCALE:
            output.append(words[i]);i+=1;continue
        # "do it", "teen drama", "char value" and "ek baat" are not quantities.
        following=key(words[i+1].text) if i+1<len(words) else ''
        if first in {'ek','do','teen','char','chaar','saat','saath','एक','दो','तीन','चार'} and following not in SCALE and following not in UNITS:
            output.append(words[i]);i+=1;continue
        j=i;total=group=0;last=None;has_scale=False;last_scale=float('inf')
        while j<len(words):
            token=key(words[j].text)
            if j>i and (words[j].start-words[j-1].end>.45 or re.search(r'[.!?;,:]$',words[j-1].text)):break
            if token in {'and','aur'} and has_scale and j+1<len(words) and key(words[j+1].text) in SMALL:
                j+=1;continue
            if token in SMALL:
                value=SMALL[token]
                if last is not None and not (last>=20 and last%10==0 and 0<value<10):break
                group+=value;last=value
            elif token in SCALE:
                scale=SCALE[token]
                if scale>=1000:
                    if scale>=last_scale:break
                    total+=(group or 1)*scale;group=0;last_scale=scale
                else:
                    if has_scale and last is None:break
                    group=(group or 1)*scale
                has_scale=True;last=None
            else:break
            j+=1
        if j==i:output.append(words[i]);i+=1;continue
        # Devanagari vowel marks are not punctuation even though Python's
        # \w excludes some combining marks (दो must become 2, not 2ो).
        leading=re.match(r'''^[([{"'“‘]*''',words[i].text)[0]
        trailing=re.search(r'''[.,!?;:)\]}"'”’।]*$''',words[j-1].text)[0]
        output.append(replace(words[i],text=leading+str(total+group)+trailing,end=words[j-1].end))
        i=j
    return output
