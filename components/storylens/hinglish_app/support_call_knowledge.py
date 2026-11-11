"""Small, local retrieval catalogue for Storylens voice support.

The sidebar IDs and controls come from static/index.html, static/app.js, and
the linked tool pages. The catalogue describes product behavior, not user
jobs, account state, or authorization to operate an editor.
"""

import re
import unicodedata


# id: (visible label, user vocabulary, purpose and first steps)
FEATURES = {
    "clean": (
        "Smart Clean", "remove silence|silence removal|dead air|silent space|silence hatao|chuppi|स्मार्ट क्लीन|खामोशी|चुप्पी|साइलेंस|खाली हिस्से",
        "Cuts silent gaps from selected videos, preserving spoken footage in order. Choose videos or a folder, check Output settings, run Smart Clean and review the resulting cut before export. Use Smart Edit when a written script should determine the order or retake choice.",
    ),
    "script": (
        "Smart Edit", "script edit|script based edit|retake|arrange clips by meaning|build by meaning|script se edit|स्मार्ट एडिट|रीटेक|स्क्रिप्ट से एडिट|स्क्रिप्ट के हिसाब",
        "Builds an editable cut by matching recorded takes to a supplied script and arranging them by meaning. Add footage and the exact script, choose pacing, run Build my timeline, and check omitted lines and selected takes before exporting.",
    ),
    "captions": (
        "Auto Captions", "caption|captions|subtitles|roman hinglish captions|captions kaise|auto caption|ऑटो कैप्शन|कैप्शन|सबटाइटल|उपशीर्षक",
        "Styles captions in English or Roman Hinglish. For the script preview, paste exact words, choose format, duration and style, then Generate captions. The script preview uses sample timing and no voice. Review the actual footage timing in an audio-aligned or native workflow before publishing.",
    ),
    "soundLibrary": (
        "Sounds", "sound library|audio library|recording permissions|साउंड लाइब्रेरी|ऑडियो लाइब्रेरी",
        "The Sounds library page organizes saved recordings, permissions and recipes. Use it when reviewing reusable audio sources. For adding music and effects to a video, open Sound Design. A library entry alone does not establish rights for your intended use.",
    ),
    "matchCut": (
        "Match Cut Finder", "match cut|matching shots|match transition|find transitions|match cut kaise|मैच कट|मिलते जुलते शॉट",
        "Finds visually similar shots across different scenes for a match-cut transition. Add a footage folder or videos, click Find matches, compare pairs, and use Export for an editable XML if needed.",
    ),
    "introCreate": (
        "Intro Create", "intro maker|intro draft|youtube intro|gaming intro|gaming cold open|instagram hook|intro kaise|इंट्रो|ओपनिंग|शुरुआती हुक",
        "Reviews and retimes Instagram Reel and YouTube drafts. For a gaming replay, choose Gaming YouTube under Intro type, select the downloaded video and click Create gaming intro. It looks for complete funny commentary and makes a 30-second opener of 3–5-second clips. Review the intro or download the editable timeline with the full replay after the opener.",
    ),
    "reelRecreate": (
        "Reel Recreate", "recreate reel|rebuild reel|beat and caption slots|reel recreate kaise|रील रीक्रिएट|रील दोबारा|रील फिर से",
        "Builds an editable recreation draft from an MP4 reference reel, with caption groups, beat intervals and footage slots. Select style, pace and speech or lyrics, use Prepare reel, review captions and beats, then add it to After Effects and replace media placeholders.",
    ),
    "referenceReel": (
        "Reference Reel", "match reference reel|reference video with my footage|reference se reel|रेफरेंस रील|संदर्भ रील",
        "Builds a draft using your footage against the timing of a reference video. Choose the reference and your footage folder, click Build reel, then compare the original and your draft before export. Reel Recreate instead prepares caption, beat and footage slots.",
    ),
    "broll": (
        "Add B-roll", "b roll|broll|supporting footage|cutaway footage|b roll kaise|बी रोल|बी रॉल|सहायक फुटेज",
        "Finds supporting footage that matches what the video says. Add the video or timeline, open B-roll settings if needed, use Find B-roll, and check suggested footage for relevance and usage rights before using it.",
    ),
    "visuals": (
        "Smart Visuals", "real photos|people photos|logos|factual visuals|smart visual|photos for narration|स्मार्ट विजुअल्स|स्मार्ट विजुअल|असली फोटो|लोगो",
        "Finds visual evidence and relevant assets such as real people, logos, and factual imagery for narration. Choose a video or timeline XML, add a script when available, run Add smart visuals and check exact identity, context, and usage rights before accepting selections.",
    ),
    "zoom": (
        "Smart Zoom", "zoom|zooms|zoom in|punch in|hide jump cuts|zoom kaise|स्मार्ट जूम|स्मार्ट ज़ूम|जूम|ज़ूम|चेहरे पर जूम",
        "Adds editable zooms for key script moments or alternate framing at cuts, with optional face focus. Choose a video or timeline XML, select the zoom strength and relevant options, run Add smart zooms and review framing and timing.",
    ),
    "sound": (
        "Sound Design", "sound effects|background music|add music|sound design kaise|sfx|साउंड डिजाइन|साउंड डिज़ाइन|बैकग्राउंड म्यूजिक|ध्वनि प्रभाव",
        "Suggests editable sound layers matched to speech and visible actions. Choose your video, select Short form or Long form and the music/effects you want, run Design the sound, and review the draft and keyword folders. Preserve the existing audio and confirm rights for additions.",
    ),
    "eyecontact": (
        "Eye Contact", "eye correction|look into camera|gaze correction|eye contact kaise|आई कॉन्टैक्ट|आँख|कैमरे में देखना|नजर",
        "Adjusts the apparent gaze of camera footage toward the lens while preserving blinks, audio and timing. Choose camera clips or a timeline XML, select where the script was relative to the lens, run Fix eye contact, and review the result. B-roll is skipped.",
    ),
    "shorts": (
        "Long to Shorts", "long video to shorts|convert to shorts|make shorts|shorts banana|shorts kaise|reels from long video|शॉर्ट्स|शॉर्ट बनाना|लंबे वीडियो से शॉर्ट|वीडियो से रील",
        "Finds standalone hook and payoff moments in a finished long MP4 or MOV. Choose the video, exact count, duration and look, use Make my shorts, then review the cut, crop and captions. This creates clips for review; use Prepare and Post separately when you want to post.",
    ),
    "motion": (
        "Motion Graphics", "animated graphics|motion graphics kaise|animate a script|मोशन ग्राफिक्स|एनिमेटेड ग्राफिक्स|मूविंग ग्राफिक्स",
        "Makes animated visuals for key moments in a story. Paste a script or select a video/timeline, choose a style, engine and preview quality, run Make motion graphics, then check the timing, text and layout before export.",
    ),
    "gaming": (
        "Gaming Highlights", "stream highlights|gameplay highlights|best gameplay moments|gaming highlights kaise|गेमिंग हाइलाइट्स|स्ट्रीम हाइलाइट्स|गेमप्ले हाइलाइट",
        "Finds strong moments in a downloaded gaming stream and prepares a highlight edit while preserving gameplay framing and stereo audio. Choose the saved stream, set highlight options, click Create highlights, and review the edit before export.",
    ),
    "thumbnail": (
        "Thumbnail", "cover image|reel cover|poster|youtube thumbnail|thumbnail kaise|थंबनेल|थम्बनेल|पोस्टर|कवर इमेज",
        "Creates YouTube thumbnails, Instagram covers, posters and social images. Choose a category and size, add your brief and any permitted references, select a style and headline option, then Create images and review the PNG or JPEG. Model availability depends on this installation.",
    ),
    "cinematic": (
        "Cinematic Footage", "best shots|footage extras|extract shots|cinematic shots|सिनेमैटिक फुटेज|बेहतरीन शॉट|बेस्ट शॉट",
        "Extracts short, visually distinct shots from footage into Best Shots and Extras. Choose a folder or videos, click Extract shots, review both groups and open the output folder to select what you want to use.",
    ),
    "slowMotion": (
        "Selective Slow Motion", "slow motion|speed ramp|speed points|slowmo|slow motion kaise|स्लो मोशन|स्पीड रैम्प|धीमी गति",
        "Finds moving moments for selective slow-downs and lets you edit speed points. Add a folder or videos, click Find moments, review recommended speeds or tune the ramp, then render previews.",
    ),
    "beats": (
        "Beat Studio", "beat markers|sync to music|detect beats|beat sync|बीट स्टूडियो|बीट मार्कर|म्यूजिक बीट",
        "Finds music beat positions and prepares optional beat-timed effects. Add the music, run Detect beats, then download marker JSON/CSV or prepare and review an effect plan.",
    ),
    "downloader": (
        "Downloader", "download video|save videos|extract audio|download youtube video|video download kaise|डाउनलोडर|वीडियो डाउनलोड|ऑडियो निकालना",
        "Saves permitted source videos or extracts audio from supported links. Paste a link, pick the format and destination, choose Add to queue, then check the result. Check permissions before downloading or reusing content.",
    ),
    "photos": (
        "Photo Collector", "screenshot photos|collect photos|images from screenshot|screenshot se photo|फोटो कलेक्टर|स्क्रीनशॉट से फोटो",
        "Collects candidate photos based on a screenshot. Choose or paste the screenshot, select Submit, then review the matches, resolution and source before selecting the photos you need.",
    ),
    "cricketDesk": (
        "Cricket Desk", "cricket news|cricket memes|cricket inbox|ipl news|क्रिकेट डेस्क|क्रिकेट न्यूज|क्रिकेट मीम|आईपीएल न्यूज़",
        "Provides an inbox for cricket news and memes. Open Cricket Desk, browse the current items, then check their dates and original sources before using them as research. It is separate from the editing and posting tools.",
    ),
    "gamingDesk": (
        "Gaming Desk", "gaming news|game releases|game updates|gaming memes|गेमिंग डेस्क|गेम रिलीज|गेम अपडेट",
        "Provides an inbox for game releases, updates and memes. Open Gaming Desk, browse or filter available items, and verify dates and original sources before using them as research. Gaming Highlights instead cuts a saved stream.",
    ),
    "callQA": (
        "Call QA", "call quality|review test calls|call recording review|call evidence|कॉल क्यूए|कॉल रिकॉर्डिंग समीक्षा|कॉल की जांच",
        "Reviews consented test-call recordings with a timed transcript, playable evidence and a QA checklist. Use Import test recording, open the call, play evidence at the relevant times, and save your review or export the anonymized report. The live Storylens Call button is separate.",
    ),
    "editorLink": (
        "Editor Handoff", "editor link|send to premiere|send to after effects|send to resolve|send to capcut|export to premiere|export to after effects|export to resolve|export to capcut|एडिटर हैंडऑफ|एडिटर में भेजना|प्रोजेक्ट ट्रांसफर",
        "Transfers compatible rendered media or editable work between Premiere Pro, After Effects, DaVinci Resolve and CapCut. Choose From and To, select the supported source, choose what to Send, then prepare the transfer and use the result's import action. Editability depends on the chosen route and format.",
    ),
    "voiceover": (
        "Voice Clone", "voiceover|voice clone kaise|script to speech|my voice|text to speech|वॉइस क्लोन|वॉइसओवर|आवाज क्लोन|अपनी आवाज",
        "Turns a written script into speech using a saved voice. Save a clear authorized 3–20 second sample of one speaker without music, choose the voice and enter the script, then Generate voice clone and listen to the result.",
    ),
    "colorGrade": (
        "Color Grade", "colour grade|color grading|colour grading|resolve lut|lut|luts|drx|कलर ग्रेड|कलर ग्रेडिंग|लट|रंग सुधार",
        "Prepares editable grading for DaVinci Resolve on a duplicate timeline. Select Color Grade 1 for RealFilm V2 on Rec.709 or Color Grade 2 for the original node structure, set the matching input profile and review settings, then apply to a duplicate or download the DRX. Presets & LUTs provides available LUT downloads.",
    ),
    "templateImport": (
        "Import Template", "template import|import templates|टेम्पलेट इम्पोर्ट|टेम्पलेट आयात",
        "Imports native template material into a connected After Effects project. Open the Storylens panel in the intended After Effects project, then run Import Template and review the result in that project before aligning or replacing its text.",
    ),
    "templateAligner": (
        "Template Aligner", "template aliner|align template|template alignment|टेम्पलेट अलाइनर|टेम्पलेट अलाइन",
        "Fits imported native templates to the edit in a connected After Effects project. Run Template Aliner after import, review folder/font status and the selected template instances, and check timing against the actual timeline.",
    ),
    "templateText": (
        "Template Text", "fill template text|replace template words|template typography|टेम्पलेट टेक्स्ट|टेम्पलेट में लिखना",
        "Fills editable text in a prepared template from the final narration. In the connected After Effects project, choose timeline audio or a narration file, run Template Text, then verify wording, timing, font and layout.",
    ),
    "copyPaste": (
        "Copy Paste", "copy media into template|paste into placeholder|replace template media|कॉपी पेस्ट|प्लेसहोल्डर बदलना",
        "Places selected source media into template placeholders in a connected After Effects project. Select and copy the source media, then select the target layer and paste. Verify framing and use Undo if the target was wrong.",
    ),
    "imageDownload": (
        "Image Downloader", "image download|download image|paste image|image address|image url|इमेज डाउनलोडर|फोटो डाउनलोड|इमेज डाउनलोड|इमेज पेस्ट",
        "Downloads a specific image from its direct address or clipboard and previews the result. In Image Downloader, paste the image or enter its address, choose Download, then review it. Photo Collector searches for candidates from a screenshot.",
    ),
    "presetLibrary": (
        "Template Library", "preset library|effect library|effects library|library templates|टेम्पलेट लाइब्रेरी|इफेक्ट लाइब्रेरी",
        "Browses reusable native template packs and their Text or Effects categories. Pick a pack, project and scene, preview the choice and insert it at the intended playhead in the connected editor. Check any required fonts and media.",
    ),
    "animationPresets": (
        "Animation Presets", "animation preset|after effects ffx|ffx presets|cc presets|एनीमेशन प्रीसेट|एनिमेशन प्रीसेट",
        "Applies native After Effects animation presets to selected layers or a new adjustment layer. Open the connected project, choose CC or Effects, select the target and preset, then verify what it changed at the intended time.",
    ),
    "importantCaptions": (
        "Important words", "important captions|important words only|keyword captions|glowing captions|महत्वपूर्ण शब्द|कीवर्ड कैप्शन|ज़रूरी शब्द",
        "Adds selective captions for meaningful words such as names, teams, scores and dates, with a glow and optional supporting sounds. Open Auto Captions → Important words, provide the source and reviewed wording, then preview timing and readability.",
    ),
    "textEffects": (
        "Cinematic Text", "cinematic text|text effects|cinematic captions|सिनेमैटिक टेक्स्ट|टेक्स्ट इफेक्ट",
        "Browses native cinematic text treatments from Auto Captions → Cinematic or the template workspace. Choose a pack/project/scene and preview the result. Native placement depends on a connected After Effects project.",
    ),
    "nativeCaptions": (
        "3D captions", "native captions|caption 3d|3d captions|three d captions|थ्री डी कैप्शन|3डी कैप्शन",
        "Uses the 3D caption choices in Auto Captions for editable native treatments. Select a 3D style and follow its editor requirements; review the text, timing and appearance before use.",
    ),
    "aivideo": (
        "AI Video", "generate video clips|ai clip generation|एआई वीडियो|एआई क्लिप",
        "Prepares generated clips from a script when the local generation tools are available. Supply the script and optionally a video or timeline for placement, select a style, and review candidate quality before using results. Availability depends on the workspace.",
    ),
    "preparePost": (
        "Prepare and Post", "publish video|posting|schedule posts|youtube upload|instagram post|upload to youtube|upload to instagram|पोस्ट शेड्यूल|वीडियो अपलोड|यूट्यूब अपलोड|इंस्टाग्राम पोस्ट|पोस्ट करना",
        "Prepares YouTube and Instagram drafts and schedules for the selected profile. Open Prepare and Post, verify Connections and the profile, choose Long or Shorts, select media, run preparation, then review copy, account, visibility and time before posting or scheduling. Instagram needs connected Chrome for its local publisher.",
    ),
    "assistant": (
        "Ask the editor", "editing assistant|editor assistant|ask editor|attach prompt|एडिटिंग असिस्टेंट|एडिटर से पूछना",
        "Accepts editing requests through the editor chat. Open Ask the editor, attach the relevant video, image, timeline or script, describe what you want, and review the plan and results. Cortana AI can explain and operate supported Storylens controls during the call.",
    ),
    "storylensCall": (
        "Voice assistant", "Cortana AI Call|Storylens Call|Cortana|voice call|ai call|live call|voice help|voice support|एआई कॉल|स्टोरीलेंस कॉल|बात करना",
        "Opens Cortana AI, the in-app voice assistant. Click Voice assistant, allow microphone access and ask a question in English, Hindi or Hinglish. Pause or resume when needed, and select End call to release the microphone. Ask what a button does or say “Press” followed by its label. Keep the call running with Minimize.",
    ),
    "profiles": (
        "Creator profiles", "profile|profile settings|creator profile|switch profiles|switch profile|change profile|cricket profile|gaming profile|प्रोफाइल बदलना|क्रिकेट प्रोफाइल|गेमिंग प्रोफाइल",
        "Keeps creator context and preferences organized by General, Cricket, or Gaming. Click Profile in the top bar, choose the intended profile, then use its shortcuts or save preferences. Check the destination account again in Prepare and Post.",
    ),
    "scheduledPosts": (
        "Scheduled posts", "view scheduled posts|post calendar|pending posts|scheduled reels|शेड्यूल किए पोस्ट|पोस्ट कैलेंडर|कतार में पोस्ट",
        "Shows saved publishing schedules and their status. Open Scheduled posts in the top bar, find the item, and confirm platform, account, and scheduled time. An item waiting in the queue has yet to publish.",
    ),
    "chatHistory": (
        "Chats", "chat history|previous chats|find old chat|चैट हिस्ट्री|पुरानी चैट|नई चैट",
        "Opens saved editing conversations. Click Chats, search and select a conversation to continue or read its transcript, or choose New chat to start separately.",
    ),
    "results": (
        "View Result and Export", "view result|open folder|export result|finished result|result folder|रिजल्ट देखें|रिज़ल्ट देखें|एक्सपोर्ट रिजल्ट",
        "Opens a completed result or sends it to an editor. After a run finishes, choose View Result to check it, use an available editor icon for handoff, or Open Folder to find the files. Export options depend on the current tool and result.",
    ),
    "activation": (
        "Storylens activation", "activation|subscription|license|licence|pricing|billing|account charge|एक्टिवेशन|लाइसेंस|सब्सक्रिप्शन|सदस्यता|कीमत",
        "The activation page describes Desktop and Editor Plugins as included for the activated computer. For activation, open the Storylens activation page and use Activate this computer. Use the Support link for current prices, payment, refunds, and account status.",
    ),
    "finance": (
        "Finance", "finance workspace|finance section|finance dashboard|freelancer finance|फाइनेंस|फ़ाइनेंस|फाइनेंस सेक्शन",
        "Finance shows monthly cash flow from Pocket Tracker and recorded net worth from Finance Tracker. Use Month and Refresh to review the summaries, or open either tracker from the links at the top for its own tools. Storylens Finance is a read-only summary.",
    ),
    "analytics": (
        "Analytics", "creator analytics|analytics dashboard|channel analytics|एनालिटिक्स|एनालिटिक्स डैशबोर्ड",
        "Reviews saved performance for the two YouTube channels and two Instagram accounts. Overview compares accounts; Analytics shows account trends and content; Reports shows monthly, quarterly, and annual results; Connections manages read permissions and Chrome reads.",
    ),
    "support": (
        "Support", "contact support|storylens support|support email|सपोर्ट",
        "Opens a Gmail draft addressed to StoryLens support. Write and review the message in Gmail before sending it.",
    ),
    "aiAgents": (
        "AI Agents", "ai agent|agents|agent suite|agent section|agents section|ai agent section|ai agents section|एआई एजेंट|ए आई एजेंट|ए आई एजेंट्स|एजेंट सूट|एजेंट सेक्शन",
        "Opens the connected Agent Suite and Comment replies workspace. It includes Editing clients, Sponsorships and SaaS sales, plus Community, Jobs, Development clients and All workflows under Developer tools. Review Connections and account-specific reply modes in Comment replies. Configured access is not proof that a platform can currently send; check the live account status before delivery.",
    ),
    "workflow": (
        "Workflow", "saved batches|scheduling and recovery", "Shows the saved publishing batches, scheduling rules and recovery status.",
    ),
    "chromePublisher": (
        "Chrome Publisher", "local publisher|instagram connection|chrome connection", "Pairs the local Chrome extension and shows its Instagram destination and saved upload tasks.",
    ),
    "stockBrowser": (
        "Stock Browser", "stock sites|stock connection", "Shows and configures the dedicated stock-site browser connection for website footage discovery.",
    ),
    "documentaryIntro": (
        "Documentary Intro", "documentary preview|documentary story review", "Reviews source spans and reference style, then prepares a documentary intro preview.",
    ),
    "nativeCuration": (
        "Native Curation", "native footage curation|native intro comparison", "Inspects native After Effects templates and saves populated projects or comparison previews.",
    ),
    "cinematicReels": (
        "Cinematic Reels", "cinematic reel assembly|assemble reel", "Detects music beats and assembles a reel from the supplied footage and selected pacing.",
    ),
}

_FEATURE_VOCABULARY = {'clean': 'smart cleanup|स्मार्ट क्लिन',
 'broll': 'b rolls|bee roll|add b roll|ऐड बी रोल',
 'motion': 'motion graphic|मोशन ग्राफ़िक्स',
 'visuals': 'smart visuals tool|स्मार्ट विज़ुअल्स',
 'thumbnail': 'ai image|ai images|image generator|thumbnail maker|एआई इमेज',
 'colorGrade': 'colour correction|color correction|color grading tool|कलर करेक्शन',
 'templateImport': 'import template tool|इम्पोर्ट टेम्प्लेट',
 'templateAligner': 'template align|template aliner tool|टेम्पलेट अलाइन',
 'presetLibrary': 'templates library|template browser|template gallery|टेम्प्लेट लाइब्रेरी',
 'preparePost': 'publishing studio|prepare post|पब्लिशिंग स्टूडियो|प्रिपेयर एंड पोस्ट',
 'editorLink': 'editor hand off|handoff|हैंडऑफ',
 'animationPresets': 'animation presets library|एनिमेशन प्रीसेट्स',
 'voiceover': 'voice flow|voice clone feature|वॉइस फ्लो',
 'photos': 'photo connector|auto connector|photo collector feature|फोटो कनेक्टर',
 'storylensCall': 'kotana|कोटाना|कोर्टाना'}
for _key, _aliases in _FEATURE_VOCABULARY.items():
    _label, _terms, _purpose = FEATURES[_key]
    FEATURES[_key] = (_label, _terms + "|" + _aliases, _purpose)

_ROUTE_ALIASES = {"effectsLibrary": "presetLibrary", "aiimage": "thumbnail"}

_CONTEXT = (
    "this tab", "current tab", "this feature", "this tool", "this screen", "which tab",
    "where am i", "what tab am i on", "what tool is this", "what does this do", "how does this work", "how do i use this",
    "ye tab", "ye feature", "ye wala", "ye kaunsa", "iska tab", "is tab", "is feature",
    "iska use", "ye kisliye", "ye kis kaam", "ye kya hai", "यह टैब", "ये टैब", "इस टैब", "ये फीचर", "इस फीचर",
    "ये वाला", "ये किसलिए", "यह किसलिए", "ये क्या है", "यह क्या है", "इसका इस्तेमाल",
    "कौन सा टैब", "किस काम आता", "किस काम का", "यह फीचर", "इस टूल",
    "इस tool", "इस tab", "इस feature", "यह tool", "यह tab", "यह feature",
    "ये tool", "ये tab", "ये feature", "इसका क्या काम", "ये क्या करता", "इससे क्या होता",
)
_FOLLOWUP = (
    "how", "why", "then", "what about", "what next", "and after", "where is it", "where do i",
    "what should i do first", "how do i start", "first step", "where do i start",
    "pehle kya", "पहले क्या", "कहाँ से शुरू",
    "how do i use it", "how does it work", "what is it for", "use it", "iska", "kaise",
    "aur", "phir", "फिर", "कैसे", "इसका", "उसका", "और", "उसके बाद", "फर्क", "अंतर",
)
_OVERVIEW = (
    "what can you do", "what can storylens do", "all features", "list features", "all tools",
    "what features", "features available", "tools available", "kya kya kar", "saare features",
    "kaun kaun se features", "sab feature", "सारे फीचर", "सभी फीचर", "कौन कौन से फीचर",
    "क्या क्या कर", "सभी टूल", "सारे टूल",
)


def _normalize(text):
    # Preserve combining vowel signs in Hindi and split punctuation in B-roll.
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    text = re.sub(r"[\u0964\u0965]", " ", text)
    return " ".join(re.sub(r"[^\w\u0900-\u097f]+|_", " ", text).split())


def _contains(query, phrase):
    return f" {_normalize(phrase)} " in query


def _lookup_terms(label, aliases):
    return tuple({_normalize(part) for part in (label, *aliases.split("|"))})


_TERMS = {
    key: _lookup_terms(label, aliases)
    for key, (label, aliases, _) in FEATURES.items()
}


def _match(query):
    hits = []
    for key, terms in _TERMS.items():
        for term in terms:
            match = re.search(rf"(?<= ){re.escape(term)}(?= )", query)
            if match:
                hits.append((match.start(), match.end(), key))
    # A shared term such as "zoom" or "captions" cannot outvote a more
    # specific match in the same place, but a separately named tool can.
    maximal = [
        (start, end, key)
        for start, end, key in hits
        if not any(a <= start and end <= b and (a, b) != (start, end) for a, b, _ in hits)
    ]
    ordered = sorted(maximal, key=lambda item: (item[0], item[2]))
    return list(dict.fromkeys(key for _, _, key in ordered))


# Source-backed nested capabilities: names are not invented top-level routes.
TOPICS = ({'name': 'Hyperframes',
  'aliases': 'hyperframes|hyperframe|hyper frame|hyper frames|हाइपर फ्रेम|हाइपरफ्रेम',
  'features': ('motion', 'captions'),
  'detail': 'Hyperframes is available in Motion Graphics → Render engine and Auto Captions → '
            'Generation method. Use the current feature to choose the intended dropdown; it is not '
            'a separate sidebar tool.',
  'source': 'index.html'},
 {'name': 'Remotion',
  'aliases': 'remotion|रीमोशन|रिमोशन',
  'features': ('motion',),
  'detail': 'Remotion is a Render engine choice inside Motion Graphics, alongside Motion Canvas '
            'and Hyperframes.',
  'source': 'index.html'},
 {'name': 'Motion Canvas',
  'aliases': 'motion canvas|motion-canvas|मोशन कैनवस',
  'features': ('motion',),
  'detail': 'Motion Canvas is a Render engine choice inside Motion Graphics.',
  'source': 'index.html'},
 {'name': '3D1 / 3D2 / 3D3',
  'aliases': '3d1|3d2|3d3|3d 1|3d 2|3d 3|three d one|three d two|three d three|थ्री डी वन|थ्री डी '
             'टू|थ्री डी थ्री',
  'features': ('nativeCaptions', 'captions'),
  'detail': '3D1, 3D2 and 3D3 are caption families inside Auto Captions. Select the family, then '
            'its available variant; these are existing caption choices, not missing standalone '
            'tools.',
  'source': 'caption-3d-catalog.json'},
 {'name': 'Important words',
  'aliases': 'important words|important captions|keyword captions|महत्वपूर्ण शब्द|जरूरी '
             'शब्द|ज़रूरी शब्द',
  'features': ('importantCaptions', 'captions'),
  'detail': 'Important words is a subtab inside Auto Captions for selective important-word '
            'captions. It has its own source, transcription and preview controls.',
  'source': 'caption-extras.js'},
 {'name': 'Cinematic captions',
  'aliases': 'cinematic captions|cinematic text|सिनेमैटिक कैप्शन',
  'features': ('textEffects', 'captions'),
  'detail': 'Auto Captions → Cinematic opens the cinematic text library. It uses the existing '
            'native text/template workspace and requires the appropriate editor connection for '
            'native placement.',
  'source': 'caption-extras.js'},
 {'name': 'Color Grade 1 / RealFilm V2',
  'aliases': 'color grade 1|colour grade 1|realfilm|real film|realfilm v2|रियलफिल्म|कलर ग्रेड वन',
  'features': ('colorGrade',),
  'detail': 'Color Grade 1 is RealFilm V2 for Rec.709 inside Color Grade; it is a choice above the '
            'node graph. Apply to duplicate timeline uses an editable grade in Resolve.',
  'source': 'color-grade.html'},
 {'name': 'Color Grade 2 / native nodes',
  'aliases': 'color grade 2|colour grade 2|19 node|nineteen node|कलर ग्रेड टू',
  'features': ('colorGrade',),
  'detail': 'Color Grade 2 is the original 19-node structure inside Color Grade. Balance, Contrast '
            'and Saturation controls apply to this structure.',
  'source': 'color-grade.html'},
 {'name': 'Presets & LUTs',
  'aliases': 'presets and luts|presets luts|lut|luts|sony looks|davinci built in luts|लट|लट्स',
  'features': ('colorGrade',),
  'detail': 'Color Grade contains Presets & LUTs, the Sony looks dropdown with Download LUT, and '
            'DaVinci Built-in LUTs. The built-in choice previews on the current Resolve clip in a '
            'separate color version; Restore previous grade returns to the prior grade.',
  'source': 'color-grade.html'},
 {'name': 'Quick Motion',
  'aliases': 'quick motion|text animations|element motion|quickmotion|क्विक मोशन|टेक्स्ट '
             'एनिमेशन|एलिमेंट मोशन',
  'features': ('presetLibrary',),
  'detail': 'Template Library → Effects contains Text Animations and Element Motion. These Quick '
            'Motion presets apply to selected native layers; controls include Word/Words scope, '
            'Duration, Motion blur, Exit and Preview motion. Current native connection and '
            'selection still matter.',
  'source': 'preset-library.js'},
 {'name': 'Editing Tools',
  'aliases': 'editing tools toolkit|effects toolkit|इफेक्ट टूलकिट',
  'features': ('presetLibrary',),
  'detail': 'Template Library → Effects includes Editing Tools, a nested toolkit beside Text '
            'Animations and Element Motion. This is inside the library rather than a separate main '
            'sidebar route.',
  'source': 'preset-library.js'},
 {'name': 'External template assets',
  'aliases': 'premiere templates|premiere pro templates|davinci templates|speed ramp '
             'templates|travel templates',
  'features': ('presetLibrary',),
  'detail': 'Template Library can display Premiere Pro, DaVinci, Speed Ramp and Travel asset '
            'sections. External pack files use Show in folder and must be opened/imported in the '
            'appropriate editor; displaying an asset does not establish cross-editor '
            'compatibility.',
  'source': 'preset-library.js'},
 {'name': 'Pocket Tracker',
  'aliases': 'pocket tracker|pocket tracking|pocket ट्रैकर|पॉकेट tracker|पॉकेट ट्रैकर|पॉकेट ट्रेकर',
  'features': ('finance',),
  'detail': 'Pocket Tracker organizes money in and out from supported bank SMS and selected Gmail alerts on the Android phone. Storylens Finance shows the paired phone ledger’s month, money in, money out, recurring amounts and budget. Open Pocket Tracker for the ledger, pairing, and reports. If the phone ledger is unavailable, check laptop pairing and refresh.',
  'voice': ('Pocket Tracker organizes income and spending from supported phone alerts. Open Finance and pick a month to see money in, money out, recurring costs and the budget.',
            'पॉकेट ट्रैकर फोन के बैंक मैसेज और चुने हुए ईमेल से आमदनी और खर्च दर्ज करता है। फाइनेंस में महीना चुनकर आमदनी, खर्च, नियमित खर्च और बजट देख सकते हैं।'),
  'source': 'finance.html'},
 {'name': 'Finance Tracker',
  'aliases': 'finance tracker|financial tracker|investment tracker|finance ट्रैकर|financial ट्रैकर|फाइनेंस tracker|फाइनेंस ट्रैकर|फ़ाइनेंस ट्रैकर|फाइनेंशियल ट्रैकर|फ़ाइनेंशियल ट्रैकर',
  'features': ('finance',),
  'detail': 'Finance Tracker tracks recorded net worth from investments, cash, deposits, personal assets and outstanding debt. In Finance, check the as-of date and missing or stale prices. Open Finance Tracker to manage the underlying records.',
  'voice': ('Finance Tracker shows recorded net worth from investments, cash, deposits, assets and debts. Open it from Finance to manage records, and check the as-of date and any missing prices.',
            'फाइनेंस ट्रैकर निवेश, नकद, जमा, संपत्ति और कर्ज़ से दर्ज कुल संपत्ति दिखाता है। रिकॉर्ड देखने या बदलने के लिए इसे फाइनेंस से खोलें और कीमतों की तारीख जाँचें।'),
  'source': 'finance.html'},
 {'name': 'Comment replies',
  'aliases': 'comment replies|reply inbox|open replies|check comments|कमेंट रिप्लाई|कमेंट का जवाब',
  'features': ('aiAgents',),
  'detail': 'AI Agents → Comment replies contains per-account connection status, reply mode, daily '
            'reply limit, Check comments, and a Reply inbox. Modes include Paused, Draft for review, '
            'and Automatic replies where available. Draft reply, Copy reply and Send reply depend on item and account readiness.',
  'voice': ('Comment replies covers the Cricket and Gaming YouTube and Instagram accounts. In AI Agents, choose Open replies to see each account’s mode, reply limit and drafts in the Reply inbox.',
            'कमेंट रिप्लाई क्रिकेट और गेमिंग के यूट्यूब और इंस्टाग्राम अकाउंट के लिए है। ए आई एजेंट्स में ओपन रिप्लाईज़ से मोड, रोज़ की सीमा और ड्राफ्ट देख सकते हैं।'),
  'source': 'ai-agents.js'},
 {'name': 'Editing clients',
  'aliases': 'editing clients|video clients|editing gigs|एडिटिंग क्लाइंट',
  'features': ('aiAgents',),
  'detail': 'AI Agents includes Editing clients for finding gigs, quoting configured rates and '
            'preparing proposals in the connected Agent Suite.',
  'voice': ('Editing clients helps find editing gigs, quote your configured rates and prepare proposals. Choose Open on its AI Agents card to review the work.',
            'एडिटिंग क्लाइंट्स एजेंट एडिटिंग के काम ढूँढने, तय रेट बताने और प्रस्ताव तैयार करने में मदद करता है। इसका कार्ड ए आई एजेंट्स में खोलें।'),
  'source': 'ai-agents.js'},
 {'name': 'Sponsorships',
  'aliases': 'sponsorship|sponsorships|sponsors|स्पॉन्सरशिप',
  'features': ('aiAgents',),
  'detail': 'AI Agents includes Sponsorships for sponsor research, draft pitches and reply '
            'tracking in the connected Agent Suite.',
  'voice': ('Sponsorships helps research sponsors, draft pitches and track replies. Choose Open on its AI Agents card to review them.',
            'स्पॉन्सरशिप्स एजेंट स्पॉन्सर ढूँढने, पिच का ड्राफ्ट बनाने और जवाब देखने में मदद करता है। इसका कार्ड ए आई एजेंट्स में खोलें।'),
  'source': 'ai-agents.js'},
 {'name': 'SaaS sales',
  'aliases': 'saas sales|saas demand research|demand research',
  'features': ('aiAgents',),
  'detail': 'AI Agents includes SaaS sales and Demand research. The local-only Storylens '
            'installation is distinct from a public product URL; promotional delivery needs '
            'current readiness.',
  'voice': ('SaaS sales helps find people whose problems StoryLens can solve. Use Demand research on its card to review those needs and prepare drafts. Public promotion needs a verified public product link.',
            'सास सेल्स एजेंट ऐसे लोग ढूँढता है जिनकी समस्या स्टोरीलेंस हल कर सकता है। कार्ड में डिमांड रिसर्च से ज़रूरतें और ड्राफ्ट देखें। प्रचार के लिए सार्वजनिक लिंक चाहिए।'),
  'source': 'ai-agents.js'},
 {'name': 'Developer agents',
  'aliases': 'developer tools|developer agents|developer section|डेवलपर टूल्स|डेवलपर एजेंट्स',
  'features': ('aiAgents',),
  'detail': 'AI Agents → Developer tools reveals Community, Jobs, Development clients and All '
            'workflows. These open the connected Agent Suite views.',
  'voice': ('In AI Agents, the three-dot Developer tools button reveals Community, Jobs, Development clients and All workflows.',
            'ए आई एजेंट्स में तीन डॉट वाला डेवलपर टूल्स बटन दबाएँ। वहाँ कम्युनिटी, जॉब्स, डेवलपमेंट क्लाइंट्स और ऑल वर्कफ़्लोज़ हैं।'),
  'source': 'ai-agents.js'},
 {'name': 'Community',
  'aliases': 'community|community agent|कम्युनिटी एजेंट',
  'features': ('aiAgents',),
  'detail': 'Community finds relevant discussions and drafts replies. It is under AI Agents → Developer tools.',
  'voice': ('Community finds relevant discussions and drafts useful replies. Open it under the three-dot Developer tools menu in AI Agents.',
            'कम्युनिटी एजेंट सही चर्चाएँ ढूँढता है और जवाब के ड्राफ्ट बनाता है। इसे ए आई एजेंट्स में तीन डॉट वाले डेवलपर टूल्स से खोलें।'),
  'source': 'ai-agents.js'},
 {'name': 'Jobs',
  'aliases': 'jobs agent|job hunter|job agent|जॉब्स एजेंट|जॉब हंटर',
  'features': ('aiAgents',),
  'detail': 'Jobs finds roles and prepares truthful applications for review. It is under AI Agents → Developer tools.',
  'voice': ('The Jobs agent finds roles and prepares truthful applications for review. Open it under Developer tools in AI Agents.',
            'जॉब्स एजेंट नौकरियाँ ढूँढता है और समीक्षा के लिए सही जानकारी वाले आवेदन तैयार करता है। इसे ए आई एजेंट्स के डेवलपर टूल्स से खोलें।'),
  'source': 'ai-agents.js'},
 {'name': 'Development clients',
  'aliases': 'development clients|development client agent|fullstack sales|डेवलपमेंट क्लाइंट्स',
  'features': ('aiAgents',),
  'detail': 'Development clients finds software development projects and prepares quotes. It is under AI Agents → Developer tools.',
  'voice': ('Development clients finds software projects and prepares quotes. Open it under Developer tools in AI Agents.',
            'डेवलपमेंट क्लाइंट्स एजेंट सॉफ्टवेयर प्रोजेक्ट ढूँढता है और कोटेशन तैयार करता है। इसे ए आई एजेंट्स के डेवलपर टूल्स से खोलें।'),
  'source': 'ai-agents.js'},
 {'name': 'All workflows',
  'aliases': 'all workflows|agent workflows|ऑल वर्कफ़्लोज़',
  'features': ('aiAgents',),
  'detail': 'All workflows opens Agent Suite views for client delivery, inbox commitments and research. It is under AI Agents → Developer tools.',
  'voice': ('All workflows brings together client delivery, inbox commitments and research in Agent Suite. Open it under Developer tools in AI Agents.',
            'ऑल वर्कफ़्लोज़ में क्लाइंट डिलीवरी, इनबॉक्स में तय काम और रिसर्च मिलते हैं। इसे ए आई एजेंट्स के डेवलपर टूल्स से खोलें।'),
  'source': 'ai-agents.js'})

def topic_matches(question):
    query = " " + _normalize(question) + " "
    return tuple(row for row in TOPICS if any(_contains(query, term) for term in row["aliases"].split("|")))


def guidance(question, active_tool="", history=()):
    """Return brief product facts for the named tool, active tab, or follow-up."""
    query = f" {_normalize(question)} "
    active = _ROUTE_ALIASES.get(active_tool, active_tool) if isinstance(active_tool, str) else ""
    if active not in FEATURES:
        active = ""
    context = any(_contains(query, phrase) for phrase in _CONTEXT)
    overview = any(_contains(query, phrase) for phrase in _OVERVIEW)
    keys = _match(query)
    topics = topic_matches(question)
    if topics:
        topic_keys = list(dict.fromkeys(key for row in topics for key in row['features']))
        if active in topic_keys:
            topic_keys.remove(active)
            topic_keys.insert(0, active)
        keys = list(dict.fromkeys(keys + topic_keys))

    if overview and not keys and not context:
        labels = ", ".join(value[0] for value in FEATURES.values())
        return "Storylens feature names for an overview. Group them by purpose and offer details on request: " + labels

    if context and active and active not in keys:
        keys.insert(0, active)
    if not keys and any(_contains(query, phrase) for phrase in _FOLLOWUP):
        for turn in reversed(tuple(history)[-6:]):
            if isinstance(turn, dict) and turn.get("role") in {"assistant", "user"}:
                keys = _match(f" {_normalize(turn.get('content', ''))} ")
                if keys:
                    break
        if not keys and active:
            keys = [active]
    if not keys:
        return ""

    facts = []
    if active:
        facts.append(f"Current app tab is {FEATURES[active][0]}.")
    facts.extend(f"{row['name']}: {row['detail']}" for row in topics[:3])
    facts.extend(f"{FEATURES[key][0]}: {FEATURES[key][2]}" for key in keys[:3])
    return "\n".join(facts)

