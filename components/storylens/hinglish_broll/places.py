"""Reject stock clips that are clearly from a different country than the video (e.g. Seoul traffic for Delhi)."""
import re

# country -> names that identify it in stock titles, tags or URLs
PLACES = {
    'india': ['india', 'indian', 'delhi', 'new delhi', 'mumbai', 'bombay', 'bangalore', 'bengaluru', 'chennai',
              'kolkata', 'hyderabad', 'pune', 'jaipur', 'goa', 'kerala', 'madurai', 'tamil nadu', 'varanasi',
              'agra', 'rajasthan', 'punjab', 'gujarat', 'ahmedabad', 'lucknow', 'hindu', 'taj mahal'],
    'usa': ['usa', 'america', 'american', 'new york', 'nyc', 'manhattan', 'brooklyn', 'los angeles', 'chicago',
            'san francisco', 'miami', 'las vegas', 'washington', 'texas', 'california', 'hollywood'],
    'canada': ['canada', 'toronto', 'vancouver', 'montreal'],
    'uk': ['london', 'england', 'british', 'scotland', 'united kingdom'],
    'france': ['france', 'paris', 'french'],
    'germany': ['germany', 'berlin', 'munich', 'german'],
    'italy': ['italy', 'rome', 'venice', 'milan', 'italian'],
    'spain': ['spain', 'barcelona', 'madrid', 'spanish'],
    'china': ['china', 'chinese', 'beijing', 'shanghai', 'hong kong', 'shenzhen'],
    'japan': ['japan', 'japanese', 'tokyo', 'osaka', 'kyoto', 'shibuya'],
    'korea': ['korea', 'korean', 'seoul', 'busan'],
    'thailand': ['thailand', 'thai', 'bangkok'],
    'vietnam': ['vietnam', 'vietnamese', 'hanoi', 'saigon'],
    'singapore': ['singapore'],
    'uae': ['dubai', 'abu dhabi', 'emirates'],
    'colombia': ['colombia', 'colombian', 'bogota', 'medellin', 'cartagena'],
    'mexico': ['mexico', 'mexican', 'cancun'],
    'brazil': ['brazil', 'brazilian', 'rio de janeiro', 'sao paulo'],
    'russia': ['russia', 'russian', 'moscow'],
    'turkey': ['turkey', 'istanbul', 'turkish'],
    'egypt': ['egypt', 'cairo', 'egyptian'],
    'australia': ['australia', 'sydney', 'melbourne', 'australian'],
    'indonesia': ['indonesia', 'bali', 'jakarta'],
    'philippines': ['philippines', 'manila'],
    'pakistan': ['pakistan', 'karachi', 'lahore'],
    'nepal': ['nepal', 'kathmandu'],
}


def _mentions(text):
    text = ' ' + re.sub(r'[^a-z]+', ' ', text.lower()) + ' '
    return {country for country, names in PLACES.items() if any(f' {n} ' in text for n in names)}


def video_country(summary):
    """The country the video is set in, from the local AI summary (e.g. 'india'), or ''."""
    mentioned = _mentions(' '.join([str(summary.get('country', ''))] + [str(p) for p in summary.get('places', [])]
                                   + [str(summary.get('visual_world', ''))]))
    return next(iter(mentioned)) if len(mentioned) == 1 else ''


def conflicts(candidate_text, country):
    """True when a clip is clearly from another country than the video."""
    if not country:
        return False
    other = _mentions(candidate_text) - {country}
    return bool(other)


TEMPLATE_WORDS = ['green screen', 'greenscreen', 'chroma', 'chroma key', 'mock up', 'mockup', 'template',
                  'placeholder', 'blank screen', 'alpha channel', 'lower third', 'intro', 'outro', 'logo reveal',
                  'transition', 'overlay', 'countdown']


def is_template(candidate_text):
    """Editing templates (green-screen TVs, mock-ups, overlays) are not B-roll."""
    text = ' ' + re.sub(r'[^a-z]+', ' ', candidate_text.lower()) + ' '
    return any(f' {word} ' in text for word in TEMPLATE_WORDS)


def with_country(queries, country):
    """Put a country-specific version of the most specific query first ("delhi street night india")."""
    if not country or not queries:
        return list(queries)
    first = queries[0]
    extra = [] if country in first.lower() else [f'{first} {country}']
    seen, result = set(), []
    for q in extra + list(queries):
        if q.lower() not in seen:
            seen.add(q.lower()); result.append(q)
    return result
