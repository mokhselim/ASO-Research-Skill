# How to build the keyword field

The keyword field is **atoms, not phrases**. Apple indexes title + subtitle + keywords as one
combined bag and forms multi-word queries from it, so any phrase whose words you already own
somewhere across the three fields is free. Writing it out again buys nothing and costs the
characters.

## Worked example

An invented bird-identification app, to show the mechanic:

    Title    (25)  BirdLens: Bird Identifier
    Subtitle (28)  Sound ID, Nests & Feeder Log
    Keywords (92)  watch,birding,species,chirp,song,call,spot,scan,
                   wild,nature,garden,tracker,list,book,seasons

That keyword field is **15 single atoms, zero multi-word entries, zero overlap with the title
or subtitle**. Terms it earns without containing any of them:

| target | how it is formed |
|---|---|
| `bird watch` | `Bird` (title) + `watch` (keywords) |
| `bird song` | `Bird` (title) + `song` (keywords) |
| `bird species` | `Bird` (title) + `species` (keywords) |
| `bird call` | `Bird` (title) + `call` (keywords) |
| `garden bird tracker` | `garden` (K) + `Bird` (T) + `tracker` (K) |
| `wild bird feeder` | `wild` (K) + `Bird` (T) + `Feeder` (subtitle) |
| `nature sound id` | `nature` (K) + `Sound` (S) + `ID` (S) |

Note that `bird identifier` — the most obvious target in the whole project — appears nowhere in
the keyword field. It is already owned by the title, so spending characters on it would be pure
waste.

Writing just those seven phrases out whole would take 96 of the 100 characters and buy nothing
the atoms do not already form — and it would leave no room for the dozens of other combinations
the same 15 atoms cover.

## The rule, precisely

1. **Title and subtitle are written for humans.** They may repeat a word for readability. That
   is fine, and it does not cost you anything in the keyword field.
2. **The keyword field is strictly atomic.** Single words only. **Zero** overlap with the title
   or subtitle. If every word of a target is already owned, the target is FREE — do not add it.
3. **Add only the missing atoms**, cheapest-per-value first, until 100 characters.
4. Script-based languages (CJK, Thai) have no word boundaries — keep those terms whole; the
   tokenizer cannot split them, and `aso fill` handles this automatically.

## Why this contradicts "keep long-tails whole"

It supersedes it, *for the keyword field*. The one thing you must not do is split a long-tail
and then fail to own the other half: a three-word target needs all three atoms present
somewhere across the three fields, or it earns nothing.

Run `aso fill` — it does this selection and reports what each target costs and what is FREE.
