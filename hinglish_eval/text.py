"""Small text rules shared by the model checks and the output checks."""
import re

# Stock sites do not know brands; B-roll search phrases must never contain them.
BRANDS = {
    'zomato', 'swiggy', 'rapido', 'uber', 'ola', 'amazon', 'flipkart', 'paytm', 'phonepe', 'gpay', 'google',
    'instagram', 'youtube', 'whatsapp', 'facebook', 'meta', 'twitter', 'netflix', 'hotstar', 'jio', 'airtel',
    'iphone', 'apple', 'samsung', 'oneplus', 'xiaomi', 'blinkit', 'zepto', 'bigbasket', 'myntra', 'nykaa',
    'oyo', 'makemytrip', 'irctc', 'indigo', 'tata', 'reliance', 'infosys', 'tcs', 'wipro', 'starbucks',
    'mcdonalds', 'dominos', 'kfc', 'cred', 'dunzo', 'urbanclap', 'linkedin', 'snapchat', 'telegram', 'tiktok',
    'chatgpt', 'openai', 'microsoft', 'nike', 'adidas', 'coca', 'pepsi', 'redbull',
}
# A B-roll "visual" must be filmable: no written text, captions or screens with words.
TEXT_WORDS = {'text', 'caption', 'captions', 'subtitle', 'subtitles', 'logo', 'logos', 'written', 'writing',
              'words', 'lettering', 'headline', 'reads', 'saying', 'signboard'}
# Words that carry no emphasis: a zoom or a sound must never land on them.
FILLERS = {
    'toh', 'to', 'matlab', 'haan', 'han', 'ji', 'okay', 'ok', 'yaar', 'na', 'hai', 'hain', 'ho', 'ki', 'ka',
    'ke', 'ko', 'se', 'me', 'mein', 'main', 'aur', 'ya', 'bhi', 'hi', 'ek', 'the', 'a', 'an', 'and', 'so',
    'like', 'um', 'uh', 'is', 'was', 'of', 'in', 'on', 'it', 'that', 'this', 'then', 'basically', 'actually',
    'wo', 'woh', 'ye', 'yeh', 'jo', 'kya', 'tha', 'thi', 'the', 'raha', 'rahi', 'rahe',
}


def tokens(text):
    return [t for t in re.sub(r'[^\w]+', ' ', str(text).casefold()).split() if t]


def word_in(word, text):
    """The word (or a clear part of it, 4+ letters) appears in the text."""
    wanted = tokens(word)
    have = tokens(text)
    if not wanted:
        return False
    for w in wanted:
        if w in have:
            continue
        if len(w) >= 4 and any(h.startswith(w[:4]) or w.startswith(h[:4]) for h in have if len(h) >= 4):
            continue
        return False
    return True


def quote_share(quote, text):
    wanted = tokens(quote)
    have = set(tokens(text))
    return sum(t in have for t in wanted) / len(wanted) if wanted else 0.0


def brands_in(text):
    return sorted({t for t in tokens(text) if t in BRANDS})


def text_words_in(text):
    return sorted({t for t in tokens(text) if t in TEXT_WORDS})


def is_filler(word):
    parts = tokens(word)
    return bool(parts) and all(p in FILLERS for p in parts)


def english_share(text):
    letters = [c for c in str(text) if c.isalpha()]
    return sum(c.isascii() for c in letters) / len(letters) if letters else 1.0


def numbers_in(text):
    return set(re.findall(r'\d+', str(text)))
