"""Separate generic scene labels from identities that footage must establish."""
import re

GENERIC=set('''a the an of in on at with and or for to from no not only same some few many
india indian city street streets road roads highway cityscape urban traffic roadside
night nighttime midnight late evening dusk daytime day dark dim quiet deserted empty closed open
unavailable light lights streetlight streetlights shop shops store stores storefront storefronts
shutter shutters cafe cafes caf coffee tea restaurant restaurants bar bars pub pubs lounge lounges
club clubs nightclub nightclubs nightlife launch interior exterior counter entrance seating table
tables dancefloor dancers neon activity view background person people man woman patrons customers
room bedroom office money phone smartphone camera filming use holding recording food animal dog
bird tree park river water train car cars vehicle vehicles bike laptop computer sky stars star
moon sun building buildings crowd bed road signs outside inside down off up still clear
real sleep asleep sleeping rest resting enjoy enjoying fun celebrate celebrating laugh laughing dance dancing'''.split())
GENERIC.update('cricket team teams game games match matches final finals season seasons tournament tournaments scoreboard display score scorecard board wicket wickets batting bowling collapse line lineup batter batsman batsmen bowler run runs cup trophy stadium fan fans first second third'.split())

# Concrete speech vocabulary, not asset choices. An exact object may not be
# replaced by its broader room/category (fridge -> kitchen, bed -> bedroom).
OBJECTS = {
    'refrigerator': ('fridge', 'refrigerator', 'refrigerators', 'fridges'),
    'washing machine': ('washing machine', 'washing machines', 'washer', 'washers'),
    'air conditioner': ('air conditioner', 'air conditioning unit', 'ac'),
    'wireless router': ('wireless router', 'router', 'wifi', 'wi fi', 'wi-fi'),
    'bed': ('bed', 'beds', 'mattress', 'bedframe'),
    'sofa': ('sofa', 'sofas', 'couch', 'couches'),
    'chair': ('chair', 'chairs'),
    'ceiling fan': ('ceiling fan', 'ceiling fans', 'pankha'),
    'television': ('television', 'tv'),
    'microwave': ('microwave', 'microwave oven'),
    'gas stove': ('gas stove', 'gas burner', 'stovetop', 'hob'),
    'wardrobe': ('wardrobe', 'wardrobes', 'almari', 'almaari', 'almirah', 'cupboard', 'closet'),
    'water heater': ('water heater', 'water heating unit', 'bathroom heater'),
}


def concrete_object(text):
    text=re.sub(r'[^a-z0-9]+',' ',str(text).casefold()).strip()
    for name,aliases in OBJECTS.items():
        if any(re.search(r'\b'+re.escape(re.sub(r'[^a-z0-9]+',' ',alias))+r'\b',text) for alias in aliases):
            return name
    return ''


def anchored_object(text):
    words=re.findall(r'[a-z0-9]+',str(text).casefold())
    tail=' '.join(words[-2:])
    for name,aliases in OBJECTS.items():
        if any(' ' in alias and tail==alias for alias in aliases):return name
    return concrete_object(words[-1]) if words else ''


def contextual_object(text, context=''):
    """Indian English 'geyser' needs a sense, rather than a literal web match."""
    if re.search(r'\bgeyser\b', str(text), re.I):
        surroundings=str(context).casefold()
        if (re.search(r'\b(?:bathroom|bath|bathing|hot water|water heater|bed|fridge|almaari|almari|flat|apartment|rent|pg)\b', surroundings)
                and not re.search(r'\b(?:yellowstone|iceland|geothermal|volcanic|hot spring)\b', surroundings)):
            return 'water heater'
    return ''


for _name,_aliases in OBJECTS.items():
    GENERIC.update(re.findall(r'[a-z0-9]+',' '.join((_name,*_aliases))))
GENERIC.update('apartment apartments flat flats housing accommodation bachelor pg refrigerator furniture kitchen appliances'.split())


def visible_object(text, wanted):
    text=re.sub(r'[^a-z0-9]+',' ',str(text).casefold()).strip()
    return any(re.search(r'\b'+re.escape(re.sub(r'[^a-z0-9]+',' ',alias))+r'\b',text)
               for alias in OBJECTS.get(wanted,(wanted,)))


def cached_scene_matches(description, keyword):
    """Recall previous pixel observations only when they mention this subject."""
    wanted=concrete_object(keyword)
    if wanted:return visible_object(description,wanted)
    families=(('room','flat','apartment','accommodation','bedroom','pg'),
              ('street','city','road','traffic'),('bar','lounge','pub'),('cafe','coffee','barista'),
              ('cricket','batting','bowling','wicket','stumps','stadium'))
    tokens=lambda s:set(re.findall(r'[a-z0-9]+',str(s).casefold()))
    need,seen=tokens(keyword),tokens(description)
    for family in families:
        if need&set(family):return bool(seen&set(family))
    need-=GENERIC&{'a','the','an','in','on','of','with','for','and'}
    return bool(need) and len(need&seen)/len(need)>=.6


def specific_subject(text):
    cleaned=re.sub(r'[^A-Za-z0-9 \-&\',]+',' ',str(text)).strip(' ,')
    cleaned=re.sub(r'\s+',' ',cleaned)[:100]
    words=set(re.findall(r'[a-z0-9]+',cleaned.casefold()))
    return cleaned if {word for word in words-GENERIC if not word.isdigit()} else ''
