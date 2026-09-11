---
name: aso-keywords
description: App Store keyword research and metadata construction — US seed pass, all-country localized expansion, title-gap selection, and title/subtitle/keyword assembly via Astro (local MCP) and Helm. Use whenever the task is ASO keyword research, choosing keywords for a store, localizing app metadata, or auditing an app's title/subtitle/keyword fields.
---

# ASO keyword research

CLI: `python3 <skill>/bin/aso` (`python <skill>\bin\aso` on Windows) · state per project in
`projects/<slug>/` · the Astro MCP address is set once by the user with `aso setup --astro-url …`
(or `ASTRO_URL`). If any command prints **"Astro is not configured"**, run `aso setup` — with no
arguments it tries Astro's documented default and tests it. If that fails, ask the user to open
Astro → Settings → MCP Server and turn on "Enable MCP Server" (and, if Astro shows a different
address, to run `aso setup --astro-url <that address>`). Never invent a host or port yourself.
Every command prints a short summary and writes files — raw data never goes into the conversation.

## Start here — the user opens with keywords

The trigger for a new project is the user sharing **one or more keywords**
("research this: hair color changer, hairstyle try on"). Those are the seeds — pass them
straight in; user-given seeds are never filtered, they get tested as-is against real popularity.

    aso init <slug> --create --name "<App> (research)" \
        --seeds "the,users,keywords" --relevance "…" --category "…"
    aso seed <slug>            # pushes the seeds to the us store, prints the pool

Ask only for what the user did not provide: app name or App Store ID, relevance stems,
category words. Then follow the flow.

## The flow

```
   0. SETUP          aso init <slug> --create --relevance "…" --category "…"
                     │  (refuses to run without relevance stems — fail closed)
                     ▼
   1. US FOUNDATION  aso seed --add … → competitors → mine → related   ◄─┐
      (go deep)      until nothing new survives                          │ loop
                     ▼                                                  ─┘
   2. LOCAL WINNERS  aso localwinners --store cc      ★ highest yield
                     who ranks HERE but not in the US → THEIR words
                     → aso verify --terms "their,words"
                     → aso mine --store cc --from-localwinners
                     ▼
   3. SELECT         aso rank (score = pop ÷ diff × (10−owners)/10)
                     aso exclude --terms … --why …    (verdicts persist)
                     ▼
   4. BUILD          aso fill  → tier1 relevant · tier2 filler brands ·
                     tier3 neutral dupes · always OLD vs NEW · snapshots
                     ▼
   5. SHIP           helm-asc (separate skill) — REPLACE the field, never append
```

## Commands

| command | what it does |
|---|---|
| `init <slug> --create --relevance … --category …` | new project; `--create` makes the Astro app (**permanent**, no delete tool) |
| `seed <slug> --add "kw,…"` | add seeds to `us`, show clean pool + UNVERIFIED bucket |
| `expand <slug> --stores cc,…` | pull per-store pools (read-only), merge into `pools.json` |
| `competitors <slug> --store cc` | top-5 apps per seed; 🆕LOCAL = ranks here, not in us |
| `mine <slug> --store cc [--from-localwinners]` | **competitor keyword extraction, any country** — aggregate vocab of apps ranking for each seed; prefiltered. `--from-localwinners` seeds with the local rivals' own words |
| `related <slug> --store cc` | Astro keyword suggestions for the seeds |
| `localwinners <slug> --store cc` | ★ local-only rivals + the vocabulary their names use, ready for `verify` |
| `verify <slug> --store cc --locale l --terms "…"` | the human step: propose native words, Astro returns real pop, ≤5 dies |
| `rank <slug> --store cc --locale l` | title-gap scoring + trap flags (top-5 names vs `category_words`) |
| `exclude <slug> --terms … --why …` | persist a rejection — never resurfaces |
| `fill <slug> --store cc --locale l --name … --subtitle … [--current …]` | **THE builder** (below) |
| `check <slug> … --keywords …` | validate any hand-written field |
| `audit <slug> --live file.json` | read-only portfolio audit: waste, violations, earned vs available, ADD/SWAP |
| `clean <slug> --store cc [--yes]` | purge irrelevant pollution from the Astro pool (destructive, gated) |
| `status <slug>` | project dashboard |

## The fill policy

`aso fill` is the only field builder. One engine (`core.build_field`), used everywhere:

1. **Tier 1 — relevant terms** (pop ≥15 first, then the 6–14 band). Atoms only, never phrases —
   Apple combines title + subtitle + keywords into one bag, so a phrase you can form is free.
2. **Tier 2 — filler brands**: competitor **products of the same category** from config
   `filler_brands`. A big app from a neighbouring category never qualifies.
3. **Tier 3 — neutral dupes**: tokens a sibling locale already owns. Harmless, fills to ~100.
   **Never leave big empty space** — but never fill with rejected or wrong-intent terms either.
- Atoms never overlap own title/subtitle; siblings on the same storefront / shared index
  (`rules/storefront-groups.json`) are auto-claimed.
  **Fill the native locale before its English sibling** (fr-CA before en-CA).
- `--current "old field"` prints **OLD vs NEW** and a ⚠ REGRESSION banner if new earns less —
  mandatory when a live field exists. Every fill writes `fill_<locale>.json` + a history snapshot.
- **One localization per locale, not per storefront.** zh-Hant ships to tw, hk and mo from a
  SINGLE field; research it against its mapped store (`rules/storefront-groups.json`,
  `zh-Hant → tw`). Filling the same locale from another store just overwrites that draft with
  one scored against the wrong pool — `fill` now warns when the store changes..
- pop 40 with 1 owner **beats** pop 70 with 10 owners. A term ten apps carry in their title
  is not an opportunity.

## Why the order matters

Translating your own concepts into a market reliably underperforms reading what the local
winners already call themselves. A market often frames the category differently rather than
translating it, and the only way to reach that framing is to harvest the vocabulary of apps
that rank there and test THEIR words. That is what step 2 is for, and it is why `localwinners`
runs before any translation pass.

## Traps

* **Never put price terms in the title or subtitle** — `free`, `gratis`, `gratuit` belong in the
  keyword field ONLY (Apple metadata guidelines). The engine may still propose phrases containing
  them for T/S; strip them and let `fill` route the atom into K.

* **Korean compounds must be SPACED.** An unspaced Korean keyword frequently reads as zero volume
  when the demand is real, and the spaced form of the same words scores normally. Always test both
  forms before calling a Korean term dead. **The rule inverts for established compounds** — a
  compound Korean has absorbed as a single lexical item wants the solid form instead. Test both,
  always.

* **Japanese compounds must be UNSPACED — the exact inverse of Korean.** A space inserted inside a
  Japanese compound drops it to the dead floor even when the solid form has real demand; this holds
  across matched pairs consistently enough to treat as a rule. But only ESTABLISHED compounds exist
  at all — an invented compound dies solid too. Test the solid form, then confirm it lives.

* **Orthography IS the keyword.** French must be tested with correct accents *and* the typographic
  apostrophe: strip either and a head term collapses to the dead floor, producing a confident but
  false DEAD verdict. The same shape as the Korean and Japanese rules above.

* **Feature-compounds are usually not searched.** People search the generic verb for the category,
  or the verb plus the thing that varies. Sell the specific use case in the screenshots; bid for
  the words people actually type.

* **English-named local winners ≠ an English-searching market.** If your seeds were English, the
  rivals you find will look English. Confirm with a native `verify` pass before believing it — and
  the converse also holds: some markets genuinely do search in English, and their local rivals have
  English names while native terms die. Read the rivals' names before proposing translations.

* **The global blocklists carry verdicts made for other apps.** A word that is "too general" for
  one category is the core intent of another, and a loose brand prefix can swallow an ordinary
  phrase. When a blocklist kills core intent, add `config.allow_terms` — phrases kept PAIRED to the
  category, never the bare word — checked after junk and before the blocklists.

* **Fail closed, always.** No relevance stems → `relevant()` raises. Every junk-in-the-pool
  incident traces back to a permissive default.
* **Relevance is per project** (`config.relevance_stems`, grows as markets are researched) —
  `app_terms` are exact-match feature words (`offline`, `ai`) that must NOT be substring stems.
* **Difficulty is inflated by adjacent categories** — read the top-5 names, not the score. A cheap
  difficulty often means a different category is answering the query.
* **CJK/Thai have no `\b`** — blocklists must substring-match non-Latin, and plurals evade a
  word-bounded ASCII pattern.
* **Cyrillic script ≠ language** — Russian and Ukrainian share a script and need per-language word
  lists (`rules/lang_filter.py`); every locale must be listed there or its own language gets
  blocked.
* **Popularity is storefront-relative.** `pop ÷ diff` ranks how cheaply you can rank in that store,
  never absolute traffic. Do not compare a score in one country to a score in another.
* **Re-score before showing** — `fill` does it automatically; never hand over a proposal without
  the OLD vs NEW line.

## Config keys (`projects/<slug>/config.json`)

`astro_app` · `asc_app` · `relevance_stems` (REQUIRED, per-language, grows) · `app_terms`
(exact-match allowlist) · `allow_terms` (un-blocks the global blocklists, category-paired) ·
`category_words` (top-5 trap check) · `filler_brands` (tier-2) · `seeds`

## Fetching live metadata for `audit`

`audit` reads a JSON list of `{locale,name,subtitle,keywords}`. If you use
[Helm](https://helm-app.com) for App Store Connect, its bundled CLI can produce it:

```bash
H=/Applications/Helm.app/Contents/Helpers/helm-asc   # adjust to your install
$H version <version-id> localizations --agent > locs.json
# then per localization id: $H localization <id> show --agent
# collect {locale,name,subtitle,keywords} into one JSON list and pass it to --live
```

Any other source works too — the file format is all `audit` cares about.
