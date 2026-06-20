# Characters — overview & new-player flow

*Design-from-scratch reference. The character domain: how a player enters, becomes a character,
and what a character *is* (a body of typed zones + installed items, on the same capability model
as rooms). This is the index/overview; the spine is `character-zones.md`. Companions to follow:
`character-emotes.md`, `character-consent.md`, `character-social.md` (relationships/titles).*

> **[BUILT]** live · **[SPLIT]** exists, reorganize · **[ROADMAP]** target.

## The idea
A character is the **body twin of a room**: the *same* zone system, but the zones are body parts,
and what you "build" into them are **items** (parts, clothing, toys, restraints, marks) that
install into **typed slots** following a hierarchy. Players enter at an **OOC/account** layer
(a café hub), make a character, learn the systems in a **tutorial**, then live IC. Everything a
character wears, grows, or is locked into is one model: *typed zones + slotted items + upgrades*,
all describable and tokened, all `escape`-reversible.

---

## 1. The OOC / account layer  [ROADMAP]
Account creation is **minimal** (nothing superfluous). A logged-in account is an **OOC avatar**
in a **café** (an OOC social hub, a normal room/realm flagged OOC, expandable later). The OOC
avatar is a *stripped character*:
- **Can:** emote, a basic self-description, chat OOC channels, **listen to IC channels** (read-only
  relay), send/receive **ograms**, set **permissions/consent defaults**, interact lightly.
- **Account features:** a **character roster** (multiple characters, fully isolated state) +
  switching; **account-default consent** each character inherits and can tighten; a **blocklist +
  content limits**; an **RP-status / away** flag; a **friends list**; a clear **OOC tag/colour** so
  IC players can tell who's OOC.
- **Ograms:** delivered **IC** (the post office is the delivery layer), with an **account-level
  notification digest** — on login the account sees *"mail pending for: <characters>"* without
  leaking content (read it IC). Cross-level *awareness*, IC *delivery*.
- **Suggestions still open:** time-zone/notification prefs, a "looking for RP" board, an onboarding
  nudge, idle handling.

## 2. Going IC the first time — the tutorial  [ROADMAP — replaces `forming.yaml`]
First time IC, the character lands in a **tutorial area** (supersedes/repairs the current Mirror
`forming`). It teaches by **using the real systems**: body zones, `{zone:}` tokens, `look`/`study`/
`handle`, `survey yourself`, emotes, installing a sample part, recoloring a sample garment, and
the quiet layers (scent/voice/touch, the presence/ambient line). **Gate progress with the reveal
primitive** (the exit out opens as each step completes); **skippable** for veterans. One source of
onboarding, and itself a showcase of the zone/item systems.

## 3. What a character starts with  [ROADMAP]
- **Default layers (the organizing roots):** `base` (the body tree), `outfit` (clothing),
  `accessories` (worn extras). The real body-part tree **nests under `base`**
  (`base → torso → chest → breast → nipples`); garments live under `outfit`; jewelry/worn items
  under `accessories`. The tutorial teaches the three layers simply, then opens the deeper tree.
- **Default body parts** (a sensible starter set under `base`), **freeform zones remain** (for
  custom zones you didn't pre-make), and **additional body parts can be bought** (see the spine).

## 4. The character-as-body model  [ROADMAP — see `character-zones.md`]
Typed, hierarchical zones + **items that install into slots** + **upgrades valid by zone-type** +
**covering that follows the tree**. Generalizes the existing `BodyModItem` (BreastItem/PenisItem/
TesticleItem) to *all* parts, clothing, toys, restraints, and marks. This is the spine — fully
specified in `character-zones.md`.

## 5. The sheet & look  [ROADMAP]
Keep `sheet` clean (name/pronouns/species/title/desc/mood/presence); move zones/worn/marks to
switches: `sheet/zones`, `sheet/worn`, `sheet/marks`, `sheet/relationships`, `sheet/consent`,
`sheet/full`. Apply the same layered de-clutter to **`look <char>`** (the appearance assembly:
desc + visible zones + worn items + marks + scent/voice), so neither dumps a wall of text.

## 6. Still-open: the social / identity half  [ROADMAP]
Not yet placed in the flow, flagged so it isn't forgotten: **relationships** (`relate`, roles
owner/peer/family, honorifics/required-address, `reputation`), **titles & faction rank**, and how
ownership (being owned by Bethany/Seraphine/another player) sits on top of relationships. Likely
IC-emergent, but wants a deliberate decision. → planned `character-social.md`.

## §0 OOC floor (character-level)
`escape`/`force_clear` always free the **person**: end the scene, relocate, clear facility/realm
state, and **defeat anything that would *trap* them** (bound-in-place, held, can't-leave) —
self-service, never gated behind staff-availability or a paid service. **Non-trapping** locks
(chastity/collar/toys) are *not* stripped by the floor — they persist as IC and come off via
key / Durgin's paid unlock / staff (good etiquette, an economy sink). Trap vs. non-trap is the
line: the floor always beats a trap; it leaves a consensual belt on you to resolve IC.

### Hardcore mode  [ROADMAP — opt-in player perm]
An **opt-in** account/character perm for players who want maximum immersion. Its **only** effect:
`escape`/`force_clear` stop doing their *item teardown* (locks/marks/installed items/worn restraints
persist as IC instead of being auto-cleared on escape). What it **never** changes:
- `escape` **still always frees the person** — ends the scene, relocates, defeats any **trap**
  (bound/held/can't-leave). Hardcore opts out of *cleanup*, never out of being freed.
- It is **self-toggleable any time** (`hardcore off`), and toggling off → `escape` performs the
  **full clean** again. Because the player can always reach the full-teardown path themselves, the
  wipe is **never gated** — that's what keeps hardcore inside §0.
- Staff/superuser purge (`force_clear(me)`/`facilityreset`) ignores hardcore entirely and always
  performs the full clean — the ultimate floor is untouched.

Detail belongs in `character-consent.md` when written; recorded here so it isn't lost.
