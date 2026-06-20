# Character Zones — the taxonomy, items, slots & upgrades (the spine)

*Design-from-scratch reference, and the spine of the character domain. A character's body is a
**typed, hierarchical zone tree**; everything worn/grown/installed/locked is an **item that
installs into a typed slot**; bodily **functions are upgrades valid only on the right zone-type**;
and **covering/reveal follow the hierarchy automatically.** Generalizes the existing `BodyModItem`.
Overview in `characters.md`. The zone *schema* itself is shared with rooms — see
`rooms-appendix.md` (zones live on rooms **and** characters).*

> **[BUILT]** live · **[SPLIT]** exists, reorganize · **[ROADMAP]** target.

## Why (the problem it solves)
Freeform-item placement was flexible but **messy** — you could install lactation on lips, guess at
zone names, leave orphaned data. The fix: make the body a **typed tree with slots**, so an item
knows *where* it goes and a function knows *what* it's valid on. No guessing, no accidents,
consistent covering — and it doubles as the engine for clothing, toys, restraints, marks, and
form-shifts. (Freeform *zones* stay, for genuinely custom spots; only the messy item *placement*
is replaced.)

---

## 1. The zone tree — layers & hierarchy  [ROADMAP; zones BUILT]
Three top-level **layers** are the organizing roots; the body nests under `base`:
```
base          ← the body itself
  torso
    chest
      breast
        nipples
    belly  (→ womb interior lives here)
  groin
    pussy / cock / balls
    anus
  head → face → mouth, eyes, ...
  limbs, ass, back, (appendages: tail, wings, ears ...)
outfit        ← clothing layer (garments install here, over base zones)
accessories   ← worn extras (jewelry, collars, leashes, plugs-as-worn ...)
```
Characters spawn with a sensible default set under `base`; **freeform zones remain** for custom
spots. (`character.db.zones` + `zone_display_order` exist today; this formalizes the hierarchy.)

## 2. Zone *types* — the slot system  [ROADMAP]
Every zone carries a **type**, which decides its valid parent and which upgrades it accepts:

| type | examples | accepts upgrades like |
|---|---|---|
| `surface` | skin, back, belly, face | marks, tattoos, sensitivity |
| `gland` | breast, nipples | lactation, production, growth, sensitivity |
| `orifice` | mouth, pussy, anus | womb-room/interior, gape/capacity, inflation, sensitivity |
| `appendage` | cock, tail, wings, ears | knot, growth, equine/draconic variants, sensitivity |

The `WombRoom`'s existing "orifice/both only" install check is the prototype — **generalize it:
every upgrade declares its valid zone-type(s),** so the system *refuses* nonsense (no lactation on
lips). Validation, not guesswork.

## 3. Items install into slots  [ROADMAP — generalize `BodyModItem`]
`BodyModItem` (BreastItem/PenisItem/TesticleItem) already installs describable, tokened parts —
**extend that to everything**. An item declares its **slot** (parent zone) and installs there:
- **Body parts** — `breast`, `nipples`, `cock`, `pussy`, `anus`, `tail`, `wings`, `ears`… each
  declares its parent (`nipples → chest/breast`, `tail → base`), so install is **slotted, never
  floating**. Buying a part installs it at the correct place with the correct type.
- **Clothing** → installs to `outfit`, over the `base` zones it covers.
- **Accessories / toys / restraints** → install to `accessories` or onto/into a target zone
  (a plug into an `orifice`, a collar to the neck).
- **Marks** → either **freeform marks** (kept) *or* a **permanent mark-install** item / a
  redescribable mark-item (the cleaner path; the facility's `record_mark`/`add_piercing` route
  through this instead of raw freeform).

Every installed item is **describable + tokened exactly like a zone** (its own `desc`/`player_desc`,
recolorable, renamable) and **removable → storage** (the `wardrobe` dict / a closet container).

## 4. Upgrades = components on a part  [ROADMAP]
Bodily **functions** are **upgrade-components** added to an installed part, valid by zone-type:
`lactation`, `milk/semen production`, `arousal/sensitivity`, `gape/capacity`, `knot`, `womb-room`,
`inflation`, growth/size, variant shaping (equine/porcine/draconic). Durgin already sells many of
these (KnotItem, GrowthSerum…) — formalize them as **upgrades that attach to the correct zone**,
not standalone guesswork. (Same mixin/component idea as rooms: a part = base item + upgrade
components.)

## 5. Covering & reveal follow the tree  [SPLIT — formalize `ancestor_covered`]
Because zones nest, **covering is structural**: a garment on `outfit` that covers `torso/chest`
hides everything under it (`breast`, `nipples`) — and lifting/removing it reveals them. Each
item declares what it **covers / doesn't cover / is covered by / purposefully reveals**, derived
from the hierarchy. (`FreeformManager._ancestor_covered` is the seed; make it the rule.) This is
also how `look`/`survey` decide what's visible.

## 6. Locks & keys  [ROADMAP — replaces plock/slock]
Real **Lock + Key items** (purchasable) instead of `plock`/`slock` commands:
- `lock <zone|item|container> with <lock>` / `unlock … with <key>`.
- **Consent-gated at placement** (player-to-player); `check_plock_consent` is the seed.
- **Removal:** the key, **or Durgin's paid unlock service** (stronger lock = higher cost) — *no
  casual OOC strip between players.*
- **§0:** the floor never strips a **non-trapping** lock (chastity/collar/toy persists, comes off
  IC) — but it always frees the **person** from anything that would **trap** them (bound-in-place,
  can't-leave), self-service, never paywalled or staff-gated. Trap vs non-trap is the line.
- Ties: economy sink (buy locks/keys, pay unlock), storage (locked containers), chastity/restraint.

## 7. Form-shifting — three tiers  [ROADMAP]
Built on the part-item model:
1. **Form presets (primary):** a "form" = a saved set of installed part-items + descs + pronouns,
   stored per character (the outfit-preset model extended to the body). `form save wolfkin` /
   `form wear human`. Covers futa-at-will, sissify, minor shifts — no extra slot; backed-up &
   floor-reversible.
2. **Hide/reveal toggles:** quick sheath/unsheath of specific zones (cock out/in, wings out/in) —
   a light toggle over tier 1.
3. **Linked alt (radical transforms, e.g. wolf):** a *second character* flagged `transform_of` the
   primary — shares identity/ownership/relationships/wallet, wholly different body/desc; swapping
   becomes it. Costs a slot; only for fundamentally-other forms.

## 8. The sheet & look (zone display)  [ROADMAP]
`sheet/zones <target>` shows the body tree separately (not dumped into the main sheet); `sheet/worn`
the installed items/clothing; `sheet/marks` the marks/piercings/brands. `look <char>` assembles
the *visible* result (desc + uncovered zones + worn items + marks + scent/voice) using the
covering rules in §5.

## Real subsystems this builds on / replaces
- **Builds on:** `BodyModItem` (the part-item seed), `WombRoom` install validation (the slot-type
  check), the shared zone schema (`_blank_zone`), `wardrobe`/`outfit_presets`, `FreeformManager`
  (freeform *zones* stay; item placement is replaced), `record_mark`/`add_piercing` (route through
  mark-items), `check_plock_consent` (the lock consent seed).
- **Replaces:** messy freeform-item placement → slotted item installs; `plock`/`slock` → lock/key
  items + Durgin unlock.

## §0 OOC floor
Form-presets, installed items, upgrades, and locks are all **backed-up and floor-reversible**;
`escape`/`force_clear` restore the body to a clean state and always free the person from any trap.
Non-trapping locks persist (resolved IC); nothing here may gate the self-service exit.

## What to carry into the fresh build
- ✅ The typed zone tree + slot system as the body's spine; items-into-slots; upgrades-by-type;
  covering-follows-tree; lock/key items; form presets.
- 🔧 Generalize `BodyModItem` → all parts/clothing/toys/marks; formalize `ancestor_covered`;
  migrate facility freeform-marks → mark-items; build the Durgin unlock service.
- ✂️ Retire freeform *item placement* (keep freeform *zones*) and `plock`/`slock`.
