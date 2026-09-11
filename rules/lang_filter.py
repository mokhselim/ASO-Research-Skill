#!/usr/bin/env python3
"""Each localization may use ONLY its own language + English. Never a third language."""
import re

SCRIPTS = {
    'arab': re.compile(r'[؀-ۿݐ-ݿ]'),
    'cyr':  re.compile(r'[Ѐ-ӿ]'),
    'hebr': re.compile(r'[֐-׿]'),
    'hang': re.compile(r'[가-힯ᄀ-ᇿ]'),
    'kana': re.compile(r'[぀-ヿ]'),
    'han':  re.compile(r'[一-鿿]'),
    'thai': re.compile(r'[฀-๿]'),
    'grek': re.compile(r'[Ͱ-Ͽ]'),
    'beng': re.compile(r'[ঀ-৿]'),
    'deva': re.compile(r'[ऀ-ॿ]'),
}
LOCALE_SCRIPT = {
    'ar-SA': 'arab', 'ru': 'cyr', 'uk': 'cyr', 'he': 'hebr', 'ko': 'hang',
    'ja': 'kana', 'zh-Hans': 'han', 'zh-Hant': 'han', 'th': 'thai', 'el': 'grek',
    'ur-PK': 'arab', 'bn-BD': 'beng', 'hi': 'deva', 'mr-IN': 'deva',
}
EXTRA_SCRIPT = {'ja': ['han'], 'ko': ['han']}

# Words used ONLY to tell apart languages that share a script (ru vs uk, es vs pt).
# Deliberately generic app-store vocabulary, never category words: a marker must be
# unique to one language and must not occur in English, or it will reject a term in
# a locale that legitimately uses it. Extend with care and re-check both properties.
LANG_MARKERS = {
    'es':  ['gratis', 'aplicación', 'aplicacion', 'mejor', 'español', 'espanol'],
    'pt':  ['grátis', 'aplicativo', 'melhor', 'português', 'portugues'],
    'fr':  ['gratuit', 'meilleur', 'français', 'francais', 'gratuite'],
    'it':  ['gratuito', 'migliore', 'italiano', 'gratuita'],
    'de':  ['kostenlos', 'einfach', 'deutsch', 'schnell'],
    'nl':  ['eenvoudig', 'nederlands', 'maken', 'handig'],
    'pl':  ['darmowy', 'najlepszy', 'polski', 'łatwy', 'latwy'],
    'cs':  ['zdarma', 'nejlepší', 'čeština', 'cestina'],
    'fi':  ['ilmainen', 'paras', 'suomi', 'helppo'],
    'da':  ['bedste', 'dansk', 'nemt'],
    'no':  ['norsk', 'enkel', 'beste'],
    'sv':  ['bästa', 'basta', 'svenska', 'enkelt'],
    'hu':  ['ingyenes', 'legjobb', 'magyar', 'egyszerű', 'egyszeru'],
    'ro':  ['română', 'romana', 'ușor', 'usor', 'cel mai bun'],
    'tr':  ['ücretsiz', 'ucretsiz', 'türkçe', 'turkce', 'kolay', 'hızlı', 'hizli'],
    'ms':  ['percuma', 'melayu', 'terbaik'],
    'id':  ['aplikasi', 'indonesia', 'mudah'],
    'vi':  ['miễn phí', 'tốt nhất', 'tiếng việt', 'dễ dàng'],
    'el':  ['δωρεάν', 'καλύτερ', 'ελληνικά'],
    'ru':  ['бесплатно', 'лучший', 'приложение', 'быстро'],
    'uk':  ['безкоштовно', 'найкращий', 'додаток', 'швидко'],
}
ALLOWED_MARKERS = {
    'en-US': [], 'en-GB': [],
    'es-MX': ['es'], 'es-ES': ['es'],
    'pt-BR': ['pt'], 'pt-PT': ['pt'],
    'fr-FR': ['fr'], 'it': ['it'], 'de-DE': ['de'], 'nl-NL': ['nl'],
    'pl': ['pl'], 'cs': ['cs'], 'fi': ['fi'], 'da': ['da'], 'no': ['no'], 'sv': ['sv'],
    'hu': ['hu'], 'ro': ['ro'], 'tr': ['tr'], 'ms': ['ms','id'], 'id': ['id','ms'], 'vi': ['vi'],
    'el': ['el'], 'ar-SA': [], 'ru': ['ru'], 'uk': ['uk'], 'he': [], 'ko': [], 'ja': [],
    'zh-Hans': [], 'zh-Hant': [], 'th': [],
    # --- added: locales that were missing entirely and so blocked their OWN language ---
    'fr-CA': ['fr'], 'en-AU': [], 'en-CA': [], 'ca': ['es'],
    'hr': [], 'sk': ['cs'], 'sl-SI': [], 'bn-BD': [], 'ur-PK': [],
    'hi': [], 'gu-IN': [], 'kn-IN': [], 'ml-IN': [], 'mr-IN': [],
    'or-IN': [], 'pa-IN': [], 'ta-IN': [], 'te-IN': [],
}

def allowed(term, locale):
    t = term.lower()
    own = LOCALE_SCRIPT.get(locale)
    ok = set([own] + EXTRA_SCRIPT.get(locale, [])) if own else set()
    for name, rx in SCRIPTS.items():
        if rx.search(term) and name not in ok:
            return False
    allow = set(ALLOWED_MARKERS.get(locale, []))
    words = set(w for w in re.split(r"[\s,:&·、，。/|\-–—()\[\]،]+", t) if w)
    words.add(t)
    for lang, marks in LANG_MARKERS.items():
        if lang in allow:
            continue
        for m in marks:
            if m in words or (" " in m and m in t):
                return False
    return True
