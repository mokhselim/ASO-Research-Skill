---
name: aso-research
description: App Store keyword research and metadata construction, worldwide — test the user's keywords, mine competitors, find native-language terms per country that no one has claimed, score by title gap, and assemble title/subtitle/keyword fields via Astro (local MCP, called directly over HTTP) and optionally Helm. Use whenever the task is ASO keyword research, choosing keywords for a store, deciding which countries to localise into, localizing app metadata, or auditing an app's title/subtitle/keyword fields.
---

# ASO keyword research

CLI: `python3 <skill>/bin/aso` (macOS only — Astro is a Mac app) · state per project in
`projects/<slug>/` · the Astro MCP address is set once by the user with `aso setup --astro-url …`
(or `ASTRO_URL`). If any command prints **"Astro is not configured"**, run `aso setup` — with no
arguments it tries Astro's documented default and tests it. If that fails, ask the user to open
Astro → Settings → MCP Server and turn on "Enable MCP Server" (and, if Astro shows a different
address, to run `aso setup --astro-url <that address>`). Never invent a host or port yourself.
Every command prints a short summary and writes files — raw data never goes into the conversation.

## Setting up — the user says "set up" or "connect"

Run `python3 <skill>/bin/aso setup` and relay its output verbatim. On `OK — Astro answered`, tell
the user they're set up and can now hand you keywords. On failure, repeat the fix the command
prints (open Astro → Settings → MCP Server → Enable) — do not guess a host or port. If your own
command sandbox blocks network access, ask the user to approve the command or allow localhost.

## How to talk to the user

The pipeline below is fixed. What this section fixes is the *conversation around it*: the
user must always know what was asked, what is being done, what is finished, what is half-done,
and what has never been touched. Follow these rules in order; none of them is optional.

### 0 · Preflight — silent, before the first question

On any invocation, before you say anything: run `aso setup` (no arguments) and
`ls <skill>/projects/`. If setup fails, relay its fix and stop — nothing else works without
Astro. If projects exist, your first question is *"Continue `<slug>`, or start a new app?"*
(one option per project, plus "New app"); on continue, jump to rule 4. Otherwise start intake.

### 1 · Intake — one short ask, then options to pick from

**Ask questions as questions, not as a form.** If your agent has an interactive question tool
(Claude Code: `AskUserQuestion`), use it for every choice below — each question gets 2–4 options
and the user can always type their own answer instead. Put the recommended option first and
mark it *(Recommended)*. Agents without such a tool: same questions in chat, options lettered
`(a) (b) (c)`, and "or type your own" after each. Never ask something the user already told
you; never ask more than one round before showing the plan.

**Round 1 — the three things only the user knows** (plain chat, one friendly message):

> Tell me three things and I'll take it from there:
> 1. **Your app** — name, or the App Store link if it's live
> 2. **What it does** — one line is enough
> 3. **The words you'd type to find it** — 2–5 seed keywords

**Round 2 — choices, as one question set** (derive the stems from their one-liner first):

| question | options (first = recommended) | free text |
|---|---|---|
| **Relevance filter** — "I'll treat a term as on-topic only if it contains one of: `bird, birding, vogel, oiseau, 野鳥, 새`. OK?" | Looks right · Let me edit them | edited stems |
| **Countries** | Suggest 3–5 for this app · US only for now · I'll list them | store codes |
| **Live listing** — "Do you have current title / subtitle / keywords?" | Not live yet — start blank · Yes, I'll paste them · Yes, read them via Helm | pasted fields |
| **Depth** | Deep on the first store, quick after · Deep everywhere · Quick everywhere | — |

*Quick* = seed → localwinners → verify → rank → fill per store. *Deep* = the full loop until
nothing new survives. If the user picked "Suggest", propose the stores with one line of
reasoning each inside the plan below — don't ask a third round.

**Round 3 — the plan, with a go/no-go question:**

```
Research plan — <app>
  seeds        bird identifier, bird sound id
  relevance    bird, birding, vogel, oiseau, 野鳥, 새
  stores       us (foundation) → jp → de → br
                 jp — biggest birding market outside the US, native-only vocabulary
                 de — …
  live fields  none — fills start from scratch
  depth        deep on us, quick on the rest
```

Then ask: **"Go ahead? This creates a permanent research app in Astro."** — options
*Go* · *Change something*. Only `Go` runs `init`.

Record the stores in the project so progress is tracked: `aso init … --stores "jp,de,br"`.
Countries added later: `aso status <slug> --stores kr`.

### 2 · Narrate every command in one line

Before each CLI call, say what it is for in plain words (*"mining the vocabulary of the apps
that rank in jp — this is where the native terms come from"*). After it, relay the command's
own summary lines — counts, top terms, `next:` hint — and nothing more. Never paste raw JSON.

### 3 · Store checkpoint — after every store, before the next one

When a store's stages are done (or you must stop mid-store), post a **store card**:

```
■ jp — done  (ja)
  found        41 native terms alive · 12 with ≤2 title owners (real gaps)
  best gaps    野鳥 図鑑 (58/22, 1 owner) · 鳥 鳴き声 (44/18, 0 owners) · …
  dead         9 proposed terms scored ≤5 — listed in localwinners_jp.json
  fields       fill_ja.json — earns 14 terms / 612 pop  (OLD 9 / 380, +232)
  needs you    3 UNVERIFIED terms: 鳥 撮影, 双眼鏡, 野鳥観察   → keep or exclude?
  next         de
```

If the card has a **needs you** line, stop and ask — as a question, not a paragraph: up to 4
terms → one multi-select question ("Which of these should I keep?"), more → the list in chat
with keep / exclude / retest per term. Do not carry decisions the user has not made into the
next store. Exclusions the user confirms go through `aso exclude … --why …` so they persist.

### 4 · The progress board is the only proof of progress

Run `aso status <slug>` and show its board (a) after every store card, (b) whenever the user
asks "where are we", and (c) **first thing when a session resumes** — before running anything
else, so the user sees the state their project is actually in. The board lists every store
the user asked for, marks each stage done or not, and names the ones that are **NOT STARTED**.
Never describe progress from memory; the board reads the files.

### 5 · Session wrap-up — never end with "done"

When the user says stop, when a wave ends, or when you are about to go quiet, post the
wrap-up. It has four parts, always in this order, and it names the untouched stores explicitly:

```
Session summary — <app>
  finished     jp (ja) · de (de-DE)              fields built, OLD vs NEW shown
  half-done    br — pool + competitors only; localwinners/verify/rank/fill still to do
  not started  kr, fr                            never touched this session
  waiting on   your call on 3 UNVERIFIED jp terms (see the jp card)
  files        projects/birdlens/ — fill_ja.json, fill_de-DE.json, rank_jp.json, …
  to resume    say "continue with br" — I'll start from where the board shows
```

Then the `aso status` board underneath it, then one question: **"What next?"** — *Continue
with <next open store>* · *Stop here* · *Ship the finished fields* (if Helm is set up). A wave
is "complete" only when every target store on the board reads *fields built*; otherwise say
which ones are not, in the wrap-up, every time.

### Decisions that are always the user's

* Creating the Astro app (`init --create`) — permanent, no delete tool.
* Any term in an **UNVERIFIED** bucket or any seed that **did NOT make the pool** — show the
  verdict and the reason, ask keep / exclude / retest. Never drop a user's word silently.
* Shipping a field that shows **⚠ REGRESSION**.
* `aso clean` — destructive; state exactly what will be removed and get a yes.
* Changing relevance stems after `init` — say what the change lets in or keeps out.

## Start here — the user opens with keywords

The trigger for a new project is the user sharing **one or more keywords**
("research this: hair color changer, hairstyle try on"). Those are the seeds — pass them
straight in; user-given seeds are never filtered, they get tested as-is against real popularity.
Keywords in the opening message answer intake item 3 — don't ask for them again. Run the
rest of the intake (rounds 1–3 above, skipping what they already told you), then:

    aso init <slug> --create --name "<App> (research)" \
        --seeds "the,users,keywords" --relevance "…" --category "…" --stores "jp,de,br"
    aso seed <slug>            # pushes the seeds to the us store, prints the pool

**Resuming** ("continue", "where were we", or any message about an existing project): run
`aso status <slug>`, show the board, and pick up at the first store that is not *fields built*.

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
| `init <slug> --create --relevance … --category … --stores …` | new project; `--create` makes the Astro app (**permanent**, no delete tool); `--stores` = the storefronts the user wants, tracked by `status` |
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
| `status <slug> [--stores cc,…]` | project dashboard + per-store progress board (done / in progress / NOT STARTED); `--stores` adds targets to track |

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
`category_words` (top-5 trap check) · `filler_brands` (tier-2) · `seeds` · `target_stores`
(what the user asked for — the progress board reports each) · `stores` (what has a pool)

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
