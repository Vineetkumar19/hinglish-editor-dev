"""Fixed product-purpose replies for voice, grounded in the feature registry.

Only explicit, simple purpose/comparison questions match. This is not a
troubleshooting, account-state, how-to, or arbitrary question answerer.
"""
import re
from difflib import SequenceMatcher
from .support_call_knowledge import FEATURES, TOPICS, _normalize

_HI = {
    'analytics': 'एनालिटिक्स में चारों क्रिएटर खातों के प्रदर्शन, रुझान, रिपोर्ट और कनेक्शन दिखते हैं।',
    'support': 'सपोर्ट से स्टोरीलेंस की सहायता टीम के नाम जीमेल ड्राफ्ट खुलता है।',
    'aiAgents': 'ए आई एजेंट्स में कमेंट रिप्लाई, एडिटिंग क्लाइंट्स, स्पॉन्सरशिप्स और सास सेल्स हैं। तीन डॉट वाले डेवलपर टूल्स में कम्युनिटी, जॉब्स, डेवलपमेंट क्लाइंट्स और ऑल वर्कफ़्लोज़ हैं।',
    'finance': 'फाइनेंस में पॉकेट ट्रैकर का महीने का कैश फ्लो और फाइनेंस ट्रैकर की दर्ज कुल संपत्ति दिखती है। ऊपर से दोनों ट्रैकर अलग से खोल सकते हैं।',
    'clean': 'स्मार्ट क्लीन वीडियो के बीच की खामोशी काटता है और बोले गए हिस्सों का क्रम बनाए रखता है।',
    'script': 'स्मार्ट एडिट आपकी लिखी स्क्रिप्ट से रिकॉर्ड किए गए टेक मिलाकर एडिट तैयार करता है।',
    'captions': 'ऑटो कैप्शन्स अंग्रेज़ी या रोमन हिंग्लिश में स्टाइल वाले कैप्शन बनाता है। स्क्रिप्ट प्रीव्यू में नमूने की टाइमिंग होती है, आवाज़ नहीं।',
    'soundLibrary': 'साउंड्स लाइब्रेरी में सेव की गई रिकॉर्डिंग, इस्तेमाल की अनुमति और साउंड की रेसिपी देख सकते हैं।',
    'matchCut': 'मैच कट फाइंडर अलग दृश्यों में दिखने वाले मिलते-जुलते शॉट ढूँढता है, ताकि उनके बीच मैच कट बना सकें।',
    'introCreate': 'इंट्रो क्रिएट में इंट्रो ड्राफ्ट देख सकते हैं और कट की टाइमिंग बदल सकते हैं। गेमिंग यूट्यूब मोड में मज़ेदार कमेंट्री के छोटे क्लिप जोड़कर तीस सेकंड का इंट्रो बनता है।',
    'reelRecreate': 'रील रीक्रिएट रेफरेंस रील से कैप्शन, बीट और फुटेज के स्लॉट वाला एडिट करने योग्य ड्राफ्ट बनाता है।',
    'referenceReel': 'रेफरेंस रील आपके फुटेज को रेफरेंस वीडियो की टाइमिंग के अनुसार लगाकर ड्राफ्ट बनाता है।',
    'broll': 'ऐड बी रोल वीडियो में कही जा रही बात के मुताबिक सहायक फुटेज ढूँढता है।',
    'visuals': 'स्मार्ट विजुअल्स कही जा रही बात के लिए असली लोगों की तस्वीरें, लोगो और संबंधित तथ्यात्मक चित्र ढूँढता है।',
    'zoom': 'स्मार्ट ज़ूम ज़रूरी बातों और कट पर एडिट करने योग्य ज़ूम लगाता है। चेहरे पर फोकस का विकल्प भी है।',
    'sound': 'साउंड डिज़ाइन बोली गई बात और दिख रहे काम के मुताबिक म्यूज़िक और साउंड इफेक्ट की एडिट करने योग्य परतें सुझाता है।',
    'eyecontact': 'आई कॉन्टैक्ट कैमरा फुटेज में नज़र को लेंस की तरफ दिखाने के लिए सुधार करता है। नतीजे को देखना ज़रूरी है।',
    'shorts': 'लॉन्ग टू शॉर्ट्स तैयार लंबे वीडियो से ऐसे छोटे हिस्से ढूँढता है जो अपने आप में पूरी बात बताते हों। पोस्ट करना अलग चरण है।',
    'motion': 'मोशन ग्राफिक्स कहानी की ज़रूरी बातों के लिए एनिमेटेड विजुअल्स बनाता है। इसमें रेंडर इंजन, स्टाइल और क्वालिटी चुन सकते हैं।',
    'gaming': 'गेमिंग हाइलाइट्स डाउनलोड की हुई गेमिंग स्ट्रीम से अच्छे पल ढूँढकर हाइलाइट एडिट तैयार करता है।',
    'thumbnail': 'थंबनेल टूल यूट्यूब थंबनेल, इंस्टाग्राम कवर, पोस्टर और सोशल मीडिया की तस्वीरें बनाता है।',
    'cinematic': 'सिनेमैटिक फुटेज आपके वीडियो से अलग दिखने वाले छोटे शॉट निकालकर बेस्ट शॉट्स और एक्स्ट्राज़ में रखता है।',
    'slowMotion': 'सेलेक्टिव स्लो मोशन चलती हुई गतिविधि के हिस्से ढूँढता है, जहाँ आप रफ़्तार घटा सकते हैं और स्पीड पॉइंट बदल सकते हैं।',
    'beats': 'बीट स्टूडियो म्यूज़िक की बीट का समय ढूँढता है और बीट के अनुसार इफेक्ट की योजना बनाने में मदद करता है।',
    'downloader': 'डाउनलोडर समर्थित लिंक से अनुमति वाले वीडियो सेव करता है या उनका ऑडियो निकालता है।',
    'photos': 'फोटो कलेक्टर स्क्रीनशॉट के आधार पर मिलती-जुलती तस्वीरों के विकल्प ढूँढता है।',
    'cricketDesk': 'क्रिकेट डेस्क क्रिकेट की खबरें और मीम्स रिसर्च के लिए एक इनबॉक्स में दिखाता है।',
    'gamingDesk': 'गेमिंग डेस्क नए गेम, अपडेट और गेमिंग मीम्स रिसर्च के लिए एक इनबॉक्स में दिखाता है।',
    'callQA': 'कॉल क्यू ए में सहमति से रिकॉर्ड की हुई टेस्ट कॉल, समय के साथ लिखा संवाद और समीक्षा के सबूत देख सकते हैं।',
    'editorLink': 'एडिटर हैंडऑफ समर्थित मीडिया या एडिट को प्रीमियर, आफ्टर इफेक्ट्स, दा विंची और कैपकट के बीच भेजता है। एडिट करने की क्षमता चुने हुए फॉर्मेट पर निर्भर है।',
    'voiceover': 'वॉइस क्लोन सेव की हुई अनुमति वाली आवाज़ में लिखी स्क्रिप्ट को बोलकर ऑडियो बनाता है।',
    'colorGrade': 'कलर ग्रेड दा विंची रिज़ॉल्व की डुप्लिकेट टाइमलाइन के लिए एडिट करने योग्य कलर ग्रेडिंग तैयार करता है।',
    'templateImport': 'इम्पोर्ट टेम्पलेट जुड़े हुए आफ्टर इफेक्ट्स प्रोजेक्ट में नेटिव टेम्पलेट सामग्री इम्पोर्ट करता है।',
    'templateAligner': 'टेम्पलेट अलाइनर इम्पोर्ट किए हुए टेम्पलेट को जुड़े हुए आफ्टर इफेक्ट्स प्रोजेक्ट की एडिट टाइमिंग में फिट करता है।',
    'templateText': 'टेम्पलेट टेक्स्ट तैयार टेम्पलेट में अंतिम नैरेशन के मुताबिक एडिट करने योग्य शब्द भरता है।',
    'copyPaste': 'कॉपी पेस्ट जुड़े हुए आफ्टर इफेक्ट्स प्रोजेक्ट में चुना हुआ मीडिया टेम्पलेट के प्लेसहोल्डर में लगाता है।',
    'imageDownload': 'इमेज डाउनलोडर सीधे इमेज लिंक या क्लिपबोर्ड से एक तस्वीर डाउनलोड करके उसका प्रीव्यू दिखाता है।',
    'presetLibrary': 'टेम्पलेट लाइब्रेरी में दोबारा इस्तेमाल करने योग्य टेम्पलेट पैक, टेक्स्ट और इफेक्ट देख सकते हैं।',
    'animationPresets': 'एनिमेशन प्रीसेट आफ्टर इफेक्ट्स की चुनी हुई लेयर या नई एडजस्टमेंट लेयर पर नेटिव प्रीसेट लगाता है।',
    'importantCaptions': 'इम्पॉर्टेंट वर्ड्स सिर्फ ज़रूरी शब्दों, जैसे नाम, टीम, स्कोर और तारीख पर चमक वाले कैप्शन लगाता है।',
    'textEffects': 'सिनेमैटिक टेक्स्ट में नेटिव टेक्स्ट स्टाइल और उनका प्रीव्यू देख सकते हैं। नेटिव प्लेसमेंट के लिए आफ्टर इफेक्ट्स कनेक्शन चाहिए।',
    'nativeCaptions': 'थ्री डी कैप्शन्स में एडिट करने योग्य नेटिव कैप्शन स्टाइल चुन सकते हैं। चुनी हुई स्टाइल की एडिटर ज़रूरतें लागू होती हैं।',
    'aivideo': 'ए आई वीडियो स्क्रिप्ट से वीडियो क्लिप तैयार करता है, जब ज़रूरी लोकल जनरेशन टूल उपलब्ध हों।',
    'preparePost': 'प्रिपेयर एंड पोस्ट चुनी हुई प्रोफाइल के लिए यूट्यूब और इंस्टाग्राम ड्राफ्ट और शेड्यूल तैयार करता है।',
    'assistant': 'आस्क द एडिटर में वीडियो, तस्वीर, टाइमलाइन या स्क्रिप्ट जोड़कर चैट के ज़रिए एडिटिंग का काम बता सकते हैं।',
    'storylensCall': 'कोर्टाना ए आई कॉल स्टोरीलेंस का वॉइस असिस्टेंट खोलता है। इससे हिंदी, अंग्रेज़ी या हिंग्लिश में बात करके समर्थित कंट्रोल चला सकते हैं।',
    'profiles': 'क्रिएटर प्रोफाइल्स जनरल, क्रिकेट और गेमिंग का संदर्भ और पसंद अलग रखती हैं। पोस्ट करने से पहले सही अकाउंट जाँचें।',
    'scheduledPosts': 'शेड्यूल्ड पोस्ट्स सेव किए हुए पोस्ट का समय और स्थिति दिखाता है। कतार में होना पोस्ट हो जाने का प्रमाण नहीं है।',
    'chatHistory': 'चैट्स में पुरानी एडिटिंग बातचीत ढूँढकर पढ़ सकते हैं, आगे बढ़ा सकते हैं या नई चैट शुरू कर सकते हैं।',
    'results': 'व्यू रिज़ल्ट एंड एक्सपोर्ट में तैयार नतीजा देख सकते हैं, उसका फोल्डर खोल सकते हैं या उपलब्ध एडिटर को भेज सकते हैं।',
    'activation': 'एक्टिवेशन पेज इस कंप्यूटर को एक्टिवेट करने के लिए है। मौजूदा कीमत, भुगतान और अकाउंट की जानकारी सपोर्ट से मिलती है।',
    'workflow': 'वर्कफ्लो सेव किए हुए पब्लिशिंग बैच, शेड्यूल के नियम और रिकवरी की स्थिति दिखाता है।',
    'chromePublisher': 'क्रोम पब्लिशर लोकल क्रोम एक्सटेंशन को जोड़ता है और इंस्टाग्राम का लक्ष्य अकाउंट व सेव किए हुए अपलोड कार्य दिखाता है।',
    'stockBrowser': 'स्टॉक ब्राउज़र वेबसाइट से फुटेज ढूँढने के लिए अलग स्टॉक साइट ब्राउज़र का कनेक्शन दिखाता और सेट करता है।',
    'documentaryIntro': 'डॉक्यूमेंटरी इंट्रो चुने हुए सोर्स हिस्से और रेफरेंस स्टाइल की समीक्षा के बाद इंट्रो प्रीव्यू तैयार करता है।',
    'nativeCuration': 'नेटिव क्यूरेशन आफ्टर इफेक्ट्स टेम्पलेट की जाँच करता है और भरे हुए प्रोजेक्ट या तुलना वाले प्रीव्यू सेव करता है।',
    'cinematicReels': 'सिनेमैटिक रील्स म्यूज़िक की बीट पहचानकर आपके फुटेज और चुनी हुई पेसिंग से रील तैयार करता है।',
}
_EN = {key: row[0] + ': ' + row[2].split('. ', 1)[0].rstrip('.') + '.'
       for key, row in FEATURES.items()}
# Keep the preview limitation explicit rather than implying audio alignment.
_EN['captions'] = 'Auto Captions styles captions in English or Roman Hinglish. Its script preview uses sample timing and no voice.'
_EN['aiAgents'] = ('AI Agents has Comment replies, Editing clients, Sponsorships and SaaS sales. '
                   'The three-dot Developer tools menu has Community, Jobs, Development clients and All workflows.')
_EN['finance'] = ('Finance shows Pocket Tracker’s monthly cash flow and Finance Tracker’s recorded net worth. '
                  'Open either tracker from the links at the top.')
_TOPICS = {row['name']: row['voice'] for row in TOPICS if 'voice' in row}
_TOPIC_TERMS = {_normalize(name): row['name'] for row in TOPICS if 'voice' in row
                for name in (row['name'], *row['aliases'].split('|'))}
_PRODUCT_SURFACES = {'finance', 'aiAgents'}
_TERMS = {}
for _key, (_label, _aliases, _) in FEATURES.items():
    for _name in (_label, *_aliases.split('|')):
        _TERMS.setdefault(_normalize(_name), set()).add(_key)
_CONTEXT = {'this', 'it', 'this feature', 'this tool', 'this tab', 'current feature',
            'current tool', 'ye', 'ye feature', 'ye tool', 'यह', 'ये', 'यह फीचर',
            'ये फीचर', 'यह टूल', 'इसका', 'इस फीचर', 'is feature', 'iska'}

def _resolve(value, active):
    name = _normalize(value)
    name = re.sub(r'^(?:the|our|हमारा|हमारे)\s+', '', name)
    if name in _CONTEXT:
        return active if active in FEATURES else ''
    candidates = _TERMS.get(name, set())
    if not candidates:
        candidates = _TERMS.get(re.sub(r'\s+(?:feature|tool|tab|फीचर|टूल)$', '', name), set())
    if candidates:
        return next(iter(candidates)) if len(candidates) == 1 else ''
    # One reproduced ASR error is context-bound and informational only. Keep
    # this out of action aliases: it must never navigate or change a setting.
    if name == 'smart plein' and active == 'clean':
        return 'clean'
    # Only a short feature name may use spelling tolerance. Extra request
    # details belong to the normal answerer, even when the name is similar.
    if len(name.split()) < 2 or len(name) > 48 or re.search(
            r'\b(?:error|failure|problem|cost|price|pricing|settings?|buttons?|options?|status|not|working|when|why|how)\b',
            name):
        return ''
    scores = {}
    for term, feature_ids in _TERMS.items():
        score = SequenceMatcher(None, name, term).ratio()
        for feature_id in feature_ids:
            scores[feature_id] = max(score, scores.get(feature_id, 0.0))
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if ranked and ranked[0][1] >= .84 and (
            len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= .10):
        return ranked[0][0]
    return ''

def corpus():
    """Public fixed guide strings eligible for persistent pre-rendering."""
    return [(text, language) for index, (language, mapping) in enumerate((('en', _EN), ('hi', _HI)))
            for text in (*mapping.values(), *(pair[index] for pair in _TOPICS.values()))]

def _subject(value, active, *, new_surfaces_only=False):
    name = _normalize(value)
    name = re.sub(r'^(?:the|my|our|हमारा|हमारे)\s+', '', name)
    subject = re.sub(r'\s+(?:feature|tool|tab|app|section|agent|फीचर|टूल|एजेंट)$', '', name)
    topic = _TOPIC_TERMS.get(name) or _TOPIC_TERMS.get(subject)
    if not topic:
        # Hindi ASR may echo the spoken “tracker” after its English spelling.
        cleaned = re.sub(r'\s+(?:tracker|ट्रैकर|ट्रेकर|क्रेकर)$', '', subject)
        candidate = _TOPIC_TERMS.get(cleaned)
        if cleaned != subject and candidate in ('Pocket Tracker', 'Finance Tracker'):
            topic = candidate
    if topic:
        return topic
    key = _resolve(name, active)
    return key if not new_surfaces_only or key in _PRODUCT_SURFACES else ''


def answer_parts(question, active='', language='en'):
    """One/two fixed purpose clips, or empty for everything beyond this scope."""
    text = str(question).strip(' \t\r\n.!?।')
    text = re.sub(r'^(?:please|can you|could you)\s+', '', text, flags=re.I)
    text = re.sub(r'^and\s+', '', text, flags=re.I)
    # Full envelopes deliberately avoid swallowing actions, failure reports,
    # follow-up details, pricing questions, and instructions embedded in quotes.
    if any(mark in text for mark in ('"', '“', '”')):
        return ()
    mapping = _HI if language == 'hi' else _EN

    def spoken(subject):
        topic = _TOPICS.get(subject)
        return topic[int(language == 'hi')] if topic else mapping.get(subject, '')

    normalized = _normalize(text)
    if re.fullmatch(
            r'(?:which|what) (?:ai )?agents (?:are (?:available|there)|do (?:i|we) have)'
            r'|(?:list|name) (?:the |my |all )?(?:ai )?agents'
            r'|what can (?:the |our )?(?:ai )?agents do'
            r'|(?:कौन कौन से|कौन से) (?:ए आई |एआई )?एजेंट(?:्स)? (?:हैं|है)', normalized):
        return (spoken('aiAgents'),)
    if re.fullmatch(r'(?:what|which agents) (?:is|are) (?:in|under) (?:the )?developer tools', normalized):
        return (spoken('Developer agents'),)

    pair = None
    for pattern in (
        r'(?:what is|what s|tell me)?\s*(?:the )?difference between (.+?) and (.+)',
        r'compare (.+?) (?:and|with|versus|vs) (.+)',
        r'how is (.+?) different from (.+)',
        r'(.+?) (?:and|versus|vs) (.+?) (?:difference|comparison)',
        r'(.+?) (?:और|aur) (.+?) (?:में|mein|me) (?:क्या |kya )?(?:अंतर|फर्क|फ़र्क|difference|farak|fark)(?: है| hain| hai)?',
    ):
        match = re.fullmatch(pattern, text, re.I)
        if match:
            pair = tuple(_subject(part, active) for part in match.groups())
            break
    keys = ()
    if pair and all(pair) and pair[0] != pair[1]:
        keys = pair
    if not keys and pair is None:
        for pattern in (
            r'what is (?:the )?(?:purpose|feature) of (.+)',
            r'what does (.+?) do',
            r'what (?:is|s) (.+?)(?: (?:for|used for))?',
            r'(?:tell me about|explain(?:ed)?|describe|what about) (.+)',
            r'what is (?:the )?(?:purpose|feature) of (.+)',
            r'(.+?) (?:क्या करता है|क्या करती है|क्या है|किसलिए है|किस काम आता है|किस काम आती है|का क्या काम है)',
            r'(.+?) (?:kya karta hai|kya karti hai|kya hai|kisliye hai|kis kaam aata hai|ka kya kaam hai)',
        ):
            match = re.fullmatch(pattern, text, re.I)
            if match:
                named = match[1]
                key = _subject(named, active)
                keys = (key,) if key else ()
                if not keys:
                    items = re.split(r'\s*,\s*(?:(?:and|और|aur)\s+)?|\s+(?:and|और|aur)\s+', named, flags=re.I)
                    if 2 <= len(items) <= 3:
                        subjects = tuple(_subject(item.strip(' ,'), active, new_surfaces_only=True)
                                         for item in items)
                        if all(subjects):
                            keys = tuple(dict.fromkeys(subjects))
                break
    if not keys and pair is None:
        for pattern in (
            r'(?:where is|where can i find|how to (?:use|find)|how (?:do|can) i (?:use|find)) (.+)',
            r'how does (.+?) work',
            r'(.+?) (?:कैसे इस्तेमाल करें|कैसे काम करता है|कैसे काम करती है|कहाँ है|कहां है|कहाँ मिलेगा)',
            r'(.+?) (?:kaise use karu|kaise use kare|kaise kaam karta hai|kahan hai|kaha hai)',
        ):
            if match := re.fullmatch(pattern, text, re.I):
                key = _subject(match[1], active, new_surfaces_only=True)
                keys = (key,) if key else ()
                break
    return tuple(reply for key in keys if (reply := spoken(key)))

def answer(question, active='', language='en'):
    return ' '.join(answer_parts(question, active, language))
