"""Shared engine: pool loading, filtering, scoring. No model needed."""
import json,os,re,sys,time
import urllib.request,urllib.error
SKILL=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(SKILL,'rules'))

def _rules(name):
    p=os.path.join(SKILL,'rules',name)
    out=[]
    for l in open(p,encoding='utf-8'):
        l=l.strip()
        if not l or l.startswith('#'): continue
        out.append(l.split('|')[0].strip().lower())
    return out

BRANDS=_rules('brands.txt')
WRONG=_rules('wrong-intent.txt')
# The rule files ship EMPTY — they are yours to fill for your own category. An empty
# list must never become re.compile(''), which matches at every position and would
# classify the entire pool as 'brand'. None means "no rule", and classify() skips it.
BRAND_RX=re.compile('|'.join(re.escape(b) for b in BRANDS),re.I) if BRANDS else None
# \b only works for ASCII. Thai/CJK/Hebrew/Arabic etc need substring matching —
# the 0x2E80 threshold missed Thai and เกม (game) sailed through \bเกม\b.
_ascii=[w for w in WRONG if w.isascii()]
_cjk=[w for w in WRONG if not w.isascii()]
WRONG_RX=re.compile('|'.join(
    ([r'\b(?:'+'|'.join(re.escape(w) for w in _ascii)+r')\b'] if _ascii else []) +
    ([ '|'.join(re.escape(w) for w in _cjk) ] if _cjk else [])),re.I) if WRONG else None

ASTRO_CONFIG=os.path.join(SKILL,'astro.json')   # written by `aso setup`, gitignored

def astro_url():
    """Where the Astro MCP server is. Nothing is baked in: every user sets their own,
    either ASTRO_URL in the environment or astro.json next to this skill (aso setup)."""
    u=os.environ.get('ASTRO_URL','').strip()
    if u: return u
    try: return (json.load(open(ASTRO_CONFIG,encoding='utf-8')).get('url') or '').strip() or None
    except (OSError,ValueError): return None

def astro_timeout():
    try: return int(os.environ.get('ASTRO_TIMEOUT') or json.load(open(ASTRO_CONFIG,encoding='utf-8')).get('timeout') or 90)
    except (OSError,ValueError): return 90

NOT_CONFIGURED=("Astro is not configured.\n"
    "  Open Astro, find the MCP server address in its settings, then run:\n"
    "    aso setup --astro-url http://<host>:<port>/mcp\n"
    "  (or set the ASTRO_URL environment variable to that address)")

def _post(url,body,headers,timeout):
    """One JSON-RPC POST. Returns (status, headers, text)."""
    req=urllib.request.Request(url,data=json.dumps(body).encode('utf-8'),method='POST',
        headers={'Content-Type':'application/json',
                 'Accept':'application/json, text/event-stream',**headers})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.status,r.headers,r.read().decode('utf-8','replace')

def _rpc_result(text):
    """Astro answers plain JSON; tolerate SSE framing (data: lines) in case a server streams."""
    text=text.strip()
    if text.startswith('{'): return json.loads(text)
    data=[l[5:].strip() for l in text.splitlines() if l.startswith('data:')]
    if not data: raise ValueError('no JSON in response')
    return json.loads(data[-1])

def _astro_once(method,params):
    """Returns (payload, err). payload is None when the call did not yield JSON.
    A fresh MCP session per call."""
    url=astro_url()
    if not url: return None,'not configured'
    t=astro_timeout()
    try:
        _,h,_=_post(url,{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
            "protocolVersion":"2025-03-26","capabilities":{},
            "clientInfo":{"name":"aso","version":"1"}}},{},t)
        sid=h.get('Mcp-Session-Id') or h.get('mcp-session-id')
        if not sid: return None,f'no session id from {url} — is this an MCP endpoint?'
        sh={'Mcp-Session-Id':sid}
        _post(url,{"jsonrpc":"2.0","method":"notifications/initialized"},sh,t)
        _,_,body=_post(url,{"jsonrpc":"2.0","id":99,"method":"tools/call",
            "params":{"name":method,"arguments":params}},sh,t)
    except urllib.error.HTTPError as e:
        return None,f'HTTP {e.code} from {url}'
    except (urllib.error.URLError,OSError,TimeoutError) as e:
        reason=getattr(e,'reason',e)
        return None,f'astro unreachable at {url} — is Astro running? ({reason})'
    try: txt=_rpc_result(body)['result']['content'][0]['text']
    except Exception: return None,'unparseable response'
    try: return json.loads(txt),None
    except Exception: return None,txt.strip()[:160]   # Astro reports failures as bare text

def astro(method,params,tries=5):
    """Astro's popularity backend fails intermittently ('Failed to fetch keyword
    popularity'). Swallowing that returns an EMPTY pool, which downstream reads as
    'every term is dead' — a silent false negative that looks like real research.
    Retry, and if it still fails, say so loudly instead of returning None quietly."""
    if not astro_url():
        print(NOT_CONFIGURED,file=sys.stderr); raise SystemExit(2)
    err=None
    for n in range(tries):
        d,err=_astro_once(method,params)
        if d is not None: return d
        if err and err.startswith('astro unreachable'): break   # retrying a dead host is noise
        if n+1<tries: time.sleep(2.0*(n+1))
    print(f"  ! astro {method} {params.get('store','')} FAILED after {tries} tries: {err}",
          file=sys.stderr)
    return None

def pool(app_id,store):
    d=astro('get_app_keywords',{'appId':str(app_id),'store':store})
    if d is None: return {}
    k=d if isinstance(d,list) else (d.get('keywords') or [])
    return {x['keyword'].strip().lower():(x.get('popularity') or 0,x.get('difficulty') or 99) for x in k}

def _add_batch(app_id,store,part):
    """One add_keywords call. Returns (confirmed_set, ok).

    'confirmed' holds ONLY keywords Astro explicitly acknowledged per-keyword. A reply
    with no 'results' array used to be read as 'all succeeded', which silently promoted
    unknown terms into the scored set — they then fell through as pop 0 and were reported
    DEAD despite never reaching the pool (de 'lieferschein', 'kassenbuch', 'angebot
    schreiben'). Unacknowledged means unknown, never dead."""
    r=astro('add_keywords',{'appId':str(app_id),'keywords':part,
                            'store':store,'platform':'iphone'},tries=2)
    if not r: return set(),False
    res=r.get('results') if isinstance(r,dict) else None
    if not res: return set(),False          # fail closed: nothing was acknowledged
    return ({str(x.get('keyword','')).strip().lower() for x in res
             if x.get('success') or x.get('error')=='Already tracked'},True)

def add(app_id,store,terms,chunk=10):
    """Returns (ok, unresolved).

    Astro fails the ENTIRE call when any single keyword's popularity lookup errors
    ('Failed to fetch keyword popularity … Astro.Errors error 7'). One poison term in a
    batch of 10 therefore loses all 10 — which looked exactly like an account-wide
    outage until 'weather' added fine while 'invoice template' never did. So: on a batch
    failure, bisect down to singles and only the genuinely bad terms end up unresolved.

    'unresolved' are terms Astro never scored — they are NOT dead and must never be
    reported as pop<=5; the caller has no data on them."""
    ok=0; unresolved=[]
    def run(part,depth=0):
        nonlocal ok
        scored,fine=_add_batch(app_id,store,part)
        if fine:
            ok+=len(scored)
            unresolved.extend(t for t in part if t.strip().lower() not in scored)
            return
        if len(part)==1:                       # isolated poison term
            unresolved.extend(part); return
        mid=len(part)//2                       # bisect: keep the good half
        time.sleep(0.5); run(part[:mid],depth+1)
        time.sleep(0.5); run(part[mid:],depth+1)
    for i in range(0,len(terms),chunk):
        if i: time.sleep(0.6)
        run(terms[i:i+chunk])
    return ok,unresolved

JUNK_RX=re.compile(r"^[\W_]+$|^.$|[\[\]{}<>|]")   # bracketed junk terms from imports
def classify(term,locale=None,min_pop=6):
    """Returns None if usable, else the reason it is excluded."""
    t=re.sub(r"\s+"," ",term.lower()).strip()   # collapse double spaces - brands hide there
    if JUNK_RX.search(t): return "junk"
    if "\u0131" in t and (locale or "")[:2]!="tr": return "artifact"  # dotless i outside Turkish
    # Project override runs AFTER junk but BEFORE the two global blocklists: those
    # encode verdicts from other apps ('camera'/'photo' = too general) and the loose
    # brand prefix 'voice tra', which swallows the ordinary phrase 'voice translator'.
    if ALLOW_RX is not None and ALLOW_RX.search(t): return None
    if BRAND_RX is not None and BRAND_RX.search(t): return 'brand'
    if WRONG_RX is not None and WRONG_RX.search(t): return 'wrong-intent'
    if locale:
        try:
            from lang_filter import allowed
            if not allowed(term,locale): return 'third-language'
        except Exception: pass
    return None

def gap_score(pop,diff,owners):
    """Scoring rule: pop 40 with 1 owner BEATS pop 70 with 10 owners.
    owners = how many of the top-10 carry the exact phrase in name+subtitle."""
    return round(pop/max(diff,1)*((10-min(owners,10))/10),3)

def title_gap(term,store,limit=10):
    # Same empty-result hazard as top_apps(): an empty search yields owners=[] , which
    # scores as the BEST possible title gap (0 owners) when in fact we have no data at
    # all. Retry, then raise — an unknown gap must never masquerade as a wide-open one.
    for _ in range(3):
        d=astro('search_app_store',{'keyword':term,'store':store,'limit':limit})
        apps=d if isinstance(d,list) else ((d or {}).get('apps') or [])
        if apps: break
        time.sleep(1.5)
    else:
        raise RuntimeError(f'no search results for {term!r} in {store} — gap UNKNOWN, not zero')
    def w(s): return set(x for x in re.sub(r'[^\w\s]',' ',(s or '').lower()).split())
    kt=w(term)
    cjk=re.search(r'[぀-ヿ一-鿿฀-๿֐-׿]',term)
    owners=[]
    for a in apps[:10]:
        blob=((a.get('name') or '')+' '+(a.get('subtitle') or ''))
        hit = term.lower() in blob.lower() if cjk else kt<=w(blob)
        if hit: owners.append((a.get('ranking'),(a.get('name') or '')[:34]))
    return owners,[(a.get('name') or '')[:24] for a in apps[:5]]

def fits(name,sub,kw):
    return len(name)<=30 and len(sub)<=30 and len(kw)<=100

def dupes(name,sub,kw):
    from collections import Counter
    toks=[t for t in re.split(r'[^\wÀ-￿]+',(name+' '+sub+' '+kw).lower()) if t]
    return {t:n for t,n in Counter(toks).items() if n>1}

def covered(term,name,sub,kw):
    blob=(name+' '+sub+' '+kw).lower()
    if re.search(r'[぀-ヿ一-鿿฀-๿֐-׿]',term): return term.lower() in blob
    have=set(x for x in re.split(r'[^\wÀ-￿]+',blob) if x)
    return set(x for x in re.split(r'[^\wÀ-￿]+',term.lower()) if x)<=have


# ---------- discovery helpers (phase 1 + 2) ----------
def _terms_from(payload):
    """extract_competitors_keywords / get_keyword_suggestions return varying shapes."""
    if payload is None: return []
    if isinstance(payload,dict):
        for k in ('keywords','suggestions','results','terms','data'):
            if k in payload: payload=payload[k]; break
        else: payload=[]
    out=[]
    for x in (payload or []):
        if isinstance(x,str): out.append(x.strip().lower())
        elif isinstance(x,dict):
            t=x.get('keyword') or x.get('term') or x.get('name') or x.get('text')
            if isinstance(t,str) and t.strip(): out.append(t.strip().lower())
    return out

def top_apps(term,store,n=5):
    # search_app_store intermittently returns a SUCCESSFUL but EMPTY result. That is
    # indistinguishable from "nothing ranks here" and reads as a real market finding —
    # pl/ru/tr each reported 0 local winners once, then 18 apiece on retry. Retry empties.
    for _ in range(2):
        d=astro('search_app_store',{'keyword':term,'store':store,'limit':10})
        apps=d if isinstance(d,list) else ((d or {}).get('apps') or [])
        if apps: break
        time.sleep(1.5)
    return [{'id':a.get('appStoreId'),'name':(a.get('name') or '')[:44],
             'subtitle':(a.get('subtitle') or '')[:40],'dev':(a.get('developer') or '')[:26],
             'rank':a.get('ranking'),'ratings':a.get('ratingCount') or 0} for a in apps[:n]]

def competitor_terms(term,store,app_id=None):
    # Astro (2026-08) made appId REQUIRED on this endpoint — without it every call
    # returns -32603 Internal error and mine reads as "0 raw terms".
    a={'keyword':term,'store':store,'platform':'iphone'}
    if app_id: a['appId']=str(app_id)
    return _terms_from(astro('extract_competitors_keywords',a))

def suggestions(term,store,app_id=None):
    a={'keyword':term,'store':store,'platform':'iphone'}
    if app_id: a['appId']=str(app_id)
    return _terms_from(astro('get_keyword_suggestions',a))

def verify_new(app_id,store,cands,existing,locale=None,floor=5,prefilter=False):
    """Add unseen candidates to Astro, read back REAL popularity, keep only >floor.
    prefilter=True drops off-topic terms BEFORE writing — mining used to pour a
    competitor's whole vocabulary into the project (vpn, chrome, netflix, pizza pizza)."""
    fresh=[c for c in dict.fromkeys(cands) if c not in existing and 0<len(c)<=36]
    if prefilter:
        fresh=[c for c in fresh if relevant(c) and classify(c,locale) in (None,'brand')]
    if not fresh: return {},[],0,[]
    add(app_id,store,fresh)
    p=pool(app_id,store)
    kept={}; dead=[]; unknown=[]
    for c in fresh:
        if c in p:
            pop,diff=p[c]
        else:
            # Not in the pool. The ONLY safe reading is 'no data'. Scoring it 0/99 here
            # is what turned three unadded German terms into confident DEAD verdicts.
            unknown.append(c); continue
        if pop>floor and not classify(c,locale): kept[c]=[pop,diff]
        else: dead.append(c)
    return kept,dead,len(fresh),unknown


_rel_lines=[l.strip() for l in open(os.path.join(SKILL,'rules','relevance.txt'),encoding='utf-8')
            if l.strip() and not l.startswith('#')]
REL_RX=re.compile('|'.join(_rel_lines),re.I) if _rel_lines else None
PROJ_RX=None             # per-project relevance regex, set by load_relevance()
def load_relevance(stems):
    """Relevance is PER PROJECT. One app's stem list is useless for another category
    and will wave neighbouring apps through as 'relevant'. Pass the project's own stems."""
    global PROJ_RX
    PROJ_RX=re.compile('|'.join(s.strip() for s in stems if s.strip()),re.I) if stems else None

ALLOW_RX=None            # per-project un-block for the global blocklists
def load_allow_terms(phrases):
    """Per-project override for brands.txt / wrong-intent.txt.

    Those files are global and record verdicts made for OTHER apps. A word banned as
    "too general" for one category is the core intent of another. Keep the phrases
    PAIRED with the category ('camera translat', not 'camera') so the bare word stays
    blocked: this un-blocks an intent, it does not open the gate."""
    global ALLOW_RX
    ALLOW_RX=re.compile('|'.join(re.escape(p.strip().lower()) for p in phrases
                                 if p.strip()),re.I) if phrases else None

APP_TERMS=set()          # per-project allowlist, set by load_app_terms()
def load_app_terms(words):
    """App-specific feature words that are relevant for THIS app but must not be
    generic relevance stems. 'offline' is the case: legitimate for an offline
    translator, but as a stem it lets in 'offline player' / 'games offline'."""
    global APP_TERMS
    APP_TERMS=set(w.strip().lower() for w in words if w.strip())

def relevant(term):
    """True = provably on-topic. False = UNVERIFIED, must be judged by a human."""
    t=term.strip().lower()
    if t in APP_TERMS: return True          # exact match only, never substring
    if PROJ_RX is None:
        raise RuntimeError(
            "no relevance_stems set for this project — refusing to guess.\n"
            "Every past junk-keyword incident traced back to a permissive default.\n"
            "Set config.json -> relevance_stems.")
    return bool(PROJ_RX.search(term))


# ---------- v2 engine: SINGLE implementations (kills the drift) ----------
CJK_RX=re.compile(r'[぀-ヿ一-鿿฀-๿֐-׿]')

def tokens(s):
    """THE tokenizer. Every command uses this one — 8 diverging lambdas caused
    the 'numbers keep changing' problem."""
    return [w for w in re.split(r'[^\w]+',(s or '').lower()) if w]

def units(t):
    """CJK/Thai/Hebrew terms have no word boundaries — keep them whole."""
    return [t] if CJK_RX.search(t) else tokens(t)

def score_field(pool,ts_text,kw,locale,excl=frozenset(),floor=5):
    """THE scoring function: what does title+subtitle+this keyword field earn
    from this store's pool? Relevant, non-excluded, rule-clean terms only."""
    blob=((ts_text or '')+' '+(kw or '')).lower()
    own=set(tokens(blob))
    earned=[]
    for t,v in pool.items():
        p,d=v[0],v[1]
        if p<=floor or t in excl: continue
        if classify(t,locale) is not None: continue
        if not relevant(t): continue
        hit = t.lower() in blob if CJK_RX.search(t) else set(tokens(t))<=own
        if hit: earned.append((p,d,t))
    earned.sort(reverse=True)
    return len(earned),sum(p for p,_,_ in earned),earned

def build_field(pool,ts_text,locale,*,claimed=frozenset(),excl=frozenset(),
                filler_rx=None,dupe_pool=(),cap=100,floor=5):
    """THE field builder — the settled policy, encoded once:
      tier 1  relevant non-brand terms (pop>=15 first, then the 6-14 band)
      tier 2  filler brands: competitor PRODUCTS of the same category only
              (the TRBRAND lesson — naver map / kakao pay never qualify)
      tier 3  neutral dupes: tokens a sibling locale already owns; harmless,
              fills the field per the 'never waste empty space' rule
    Atoms never overlap title/subtitle or claimed sibling atoms. CJK kept whole.
    Returns (atoms, tags) where tags[atom] in {relevant, brand, neutral}."""
    blob=(ts_text or '').lower()
    ts_own=set(tokens(blob))
    have=ts_own|set(claimed)
    field=[]; tags={}
    def try_add(t,tier):
        # CJK units have no token boundaries — a unit already SUBSTRING-present in
        # title/subtitle or the field is a duplicate (髪型診断 was re-added next to
        # a subtitle that contained it)
        cur=','.join(field)
        need=[u for u in units(t) if u not in have and u not in field
              and not (CJK_RX.search(u) and (u in blob or u in cur))]
        # a multi-word brand/relevant term must not drag third-language atoms in
        # (e.g. a French phrase adding French atoms to en-CA)
        need=[u for u in need if classify(u,locale)!='third-language']
        if not need: return
        if len(','.join(field+need))>cap: return
        for u in need: field.append(u); tags[u]=tier
        have.update(need)
    def ok(t,p): return p>floor and t not in excl and 0<len(t)<=36
    t1=[(v[0],t) for t,v in pool.items() if ok(t,v[0])
        and classify(t,locale) is None and relevant(t)]
    for band in (15,0):
        for p,t in sorted([c for c in t1 if c[0]>=band],reverse=True):
            try_add(t,'relevant')
    if filler_rx is not None:
        t2=[(v[0],t) for t,v in pool.items() if ok(t,v[0])
            and classify(t,locale)=='brand' and filler_rx.search(t)]
        for p,t in sorted(t2,reverse=True): try_add(t,'brand')
    # an excluded BARE atom (room, planner) is still legitimate as a unit of an
    # alive non-excluded phrase in THIS pool (room planner 40/13 on kr) — the
    # exclusion said "unwinnable standalone target", not "wrong intent anywhere".
    # unblur-class exclusions stay blocked: no living phrase contains them.
    phrase_units=set()
    for t,v in pool.items():
        if v[0]>floor and ' ' in t and t not in excl \
           and classify(t,locale) is None and relevant(t):
            phrase_units.update(u.lower() for u in units(t))
    for a in dupe_pool:
        a=(a or '').strip().lower()
        if not a or ' ' in a or len(a)<2: continue
        # dupes are DELIBERATE duplicates of sibling-claimed atoms — block only
        # the own title/subtitle, atoms already in this field, and excluded verdicts
        # (an exclusion outranks 'harmless': unblur leaked into 4 locales this way)
        if a in ts_own or a in field or (a in excl and a not in phrase_units): continue
        if classify(a,locale) in ('wrong-intent','third-language','junk','artifact','brand'): continue
        if len(','.join(field+[a]))>cap: continue
        field.append(a); tags[a]='neutral'; have.add(a)
    return field,tags

PRICE_RX=re.compile(r'\bfree\b|\bgratis\b|\bgratuit\w*\b|\bgr[áa]tis\b|kostenlos|ücretsiz|ucretsiz|'
 r'бесплатн|безкоштовн|darmow|za darmo|zdarma|zadarmo|ingyenes|δωρεάν|ilmainen|percuma|'
 r'besplatno|brezpla|мајани|مجاني|مجانا|חינם|무료|無料|免费|免費|miễn phí|ฟรี',re.I)
def validate(name,sub,kw,locale):
    """Every hard rule in one place. Returns a list of error strings (empty = clean)."""
    errs=[]
    if PRICE_RX.search(name+' '+sub):
        errs.append("price term (free/gratis/…) in title or subtitle — keyword field ONLY")
    if len(name)>30: errs.append(f"title {len(name)}/30 OVER")
    if len(sub)>30: errs.append(f"subtitle {len(sub)}/30 OVER")
    if len(kw)>100: errs.append(f"keywords {len(kw)}/100 OVER")
    ts=set(tokens(name+' '+sub))
    ov=[a for a in kw.split(',') if a and a.lower() in ts]
    if ov: errs.append(f"overlap with title/subtitle: {ov}")
    from collections import Counter
    dup=[a for a,n in Counter([a for a in kw.split(',') if a]).items() if n>1]
    if dup: errs.append(f"repeated atoms: {dup}")
    lg=[a for a in kw.split(',') if a and classify(a,locale)=='third-language']
    if lg: errs.append(f"third-language: {lg}")
    return errs

def remove(app_id,store,terms,chunk=20):
    """remove_keywords wrapper — DESTRUCTIVE, callers must gate on --yes."""
    done=0
    for i in range(0,len(terms),chunk):
        r=astro('remove_keywords',{'appId':str(app_id),'keywords':terms[i:i+chunk],
                                   'store':store,'platform':'iphone'})
        if r is not None: done+=len(terms[i:i+chunk])
    return done
