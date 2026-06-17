# Rooms & Room-Zones

*Status: PROVEN — the core system is built, live, and well-liked. This blueprint captures it
as-is, plus the agreed improvements as a clearly-marked ROADMAP. Companion files:
`rooms-appendix.md` (full field/verb reference), `maze-gating.md` (the gate guide),
`gate-conditions.md` (condition types).*

> Legend: **[BUILT]** = works in the live game today. **[ROADMAP]** = agreed improvement,
> not yet built. Keep them honest — don't build the fresh copy assuming ROADMAP exists.

---

## The idea
A room (and a *body*) isn't one block of description — it's a set of named **zones**, and each
zone carries layered, discoverable content: prose to **look** at, details to **examine**,
observations that reward a **study**, things you can **handle**, scents to **smell**, surfaces
to **interact** with (seats, machines), and writing you can **inscribe**. Description becomes
*exploration*: the room rewards attention, and ANSI-coloured nouns are the breadcrumb. The same
schema lives on characters, so a body is as explorable as a room.

The deeper principle we landed on: **one universal `reveal`/`gate` condition** (see
`gate-conditions.md`) can be bolted onto *anything* interactable — a detail, a handle, a study,
a mechanic, or an exit — so the world **unfolds by state and by action** and always **fails
open** (never traps). [PARTLY BUILT — see Reveal/Gate below.]

---

## How it works [BUILT]

### Holders & the zone dict
- Zones live on `room.db.zones` **and** `character.db.zones` — a dict keyed by lowercase zone
  name → a **zone dict** (`commands/roomzone_commands.py::_blank_zone`). Full field list in
  `rooms-appendix.md`. The big ones: `desc`, `summary`, `details` (name→text, look-able),
  `handle_details` (name→intimate emote), `study_details` (list of random observations),
  `inscribable`/`inscriptions`, `scent`, `ambient` (passive lines), `mechanics` (seats/machines/
  womb_room/**triggers**), `parent` (nesting), `time_descs` (time-of-day descs).
- Zones nest via `parent`; depth is tracked (cycle-safe).

### Rendering (what shows in `look`)
- Auto-append is **disabled by design**. A zone's prose only appears when you place a
  `{zone:<name>}` token in the room's `@desc`, or via `look <zone>`. **ANSI colour on the
  interactable nouns is the intended cue.** (`typeclasses/rooms.py::_render_zone_tokens`.)
- The `{zone:<name>}` token resolves by priority: `time_descs[current_period]` → `summary` →
  `desc` → "". Also supports `{time}` and `{weather}` tokens.

### Player verbs [BUILT]
- `look` / `examine <detail>` — a zone detail (text; no object needed). `look <name> in <zone>`
  disambiguates.
- `study <zone>` — a random line from `study_details` (+ shows inscriptions).
- `handle <detail>` — the intimate emote from `handle_details`; can fire a zone **trigger**
  (`set_attr` / `reveal_item` — handling uncovers a stashed object that may carry binding_effects).
- `smell` / `sniff` — zone `scent`.
- `touch`/`caress`/`grope`/`stroke`/`grab`/`squeeze`/`kiss`/`bite`/`lick`/`taste`/`pull`/
  `pinch`/`nuzzle`/`hold`/`pet` — the body-zone emote verb-set (`CmdZoneInteract`), targets a
  **character's** zones, fills pronoun/name tokens, with `/quiet` `/private` `/self` switches.
- `inscribe` — write into an `inscribable` zone (shown via `study`).
- `survey` / `scan` / `discern` — **[BUILT this session]** lists what's lookable / studiable /
  handleable / inscribable / interactable here or on a target; deliberately **hides** trigger
  interactions (no spoiling reach-to-find things).

### Builder verbs [BUILT]
`roomzone` / `rz` (Builders + room owner): `desc`, `detail [/rm]`, `add [in <parent>]`, `rm`,
`scent [/clear]`, `ambient [/clear]`, `token`, `handle [/rm]`, `study [/rm] [/list]`,
`inscribe/enable|disable|list`, `summary`, `timedesc [/rm] [/list]`, plus `bar`/`game`/`pantry`.
Full syntax in `rooms-appendix.md`.

### Real subsystems that hang off zones [BUILT]
Freeform marks/piercings/brands (`FreeformManager` writes into a zone), seat/restraint/milking
mechanics, `WombRoom` (installed on an orifice zone), inflation (orifice zones), CYOA scenes
(rooms host them), waystones, AmbientScript, weather/time. **Zones are the universal anchor.**

---

## The Reveal / Gate primitive — the centerpiece

A small condition that can hide/lock an interactable until it's satisfied, and **fails open**.

- **[BUILT] on maze exits:** `maze gate <name> = <type> [<min>]` — a solved path won't open
  until a body condition is met (`conditioning|regression|devotion|standing|quota`). Errors →
  opens. See `maze-gating.md`.
- **[BUILT] on handles, narrowly:** the `reveal_item` trigger (handle → uncover a stashed object).
- **[ROADMAP] generalize it to everything:** the same condition dict on a *detail*, *handle*,
  *study*, *mechanic*, or *ordinary exit*, so it's hidden from `look`/`survey` until unlocked by
  a **state** (conditioning ≥ N…), a **prereq** ("studied this zone"), an **action** ("sat
  down"), or a **held item**. Worked examples:
  - *The wall-words:* `look wall` shows nothing extra until conditioning crosses a threshold —
    then a subliminal detail appears that only the deep ones can see (pairs with viewer-aware
    descs below).
  - *The hidden exit:* one exit, invisible and absent from `survey`, revealed by `study`ing the
    right surface or meeting a condition — far cheaper than dummy rooms or lock-wrangling.
  - *The jacuzzi:* a `DildoSeatMechanic` (already orifice-aware — it reads the sitter's
    groin-parented orifice zone and engages anal/vaginal accordingly) whose dildos are an
    **undescribed, surveyed-hidden** detail until you `sit` — the surprise is the reveal-on-action.

See `gate-conditions.md` for the condition catalogue (built + proposed).

---

## ROADMAP (agreed improvements, not yet built)
1. **[ROADMAP] Unify room-zones & body-zones.** Make `look`/`study`/`handle`/`survey` resolve
   against a room zone *or* a target's body via `'s` syntax (`study helena's brand`), so a body
   is as inspectable as a room (keeping the `touch/kiss` emote set too). Consent/relationship
   gating can ride on handling someone. *(Today `study`/`handle` are room-only; the emote verbs
   are body-only — that's the asymmetry to close.)*
2. **[ROADMAP] State- & viewer-aware descs.** Extend the `time_descs` pattern: a zone renders
   differently by **room state** (flooded/filthy/occupied) and by **viewer state** (a
   conditioned/little/owned looker sees a subliminal `|x` layer a free one doesn't). Render
   priority becomes: viewer-state → room-state → time → summary → desc.
3. **[ROADMAP] Progressive/gated discovery.** The Reveal/Gate primitive on details/handles/
   studies (above) — rooms unfold the more you attend, deeper conditioning sees more.
4. **[ROADMAP] Fuller senses.** Add `listen` (sound field; `ambient` already exists), `taste`,
   `feel` (temperature/texture) as verbs + optional zone fields — completes what `smell` started.
5. **[ROADMAP — likely skip] Zones that remember** (wear/use-count nudging the desc). Heaviest,
   least essential.
6. **[ROADMAP] `rz export`.** Walk a built room and emit **every piece of prose as the exact
   `roomzone`/`rz` commands that placed it** (desc, details, handle, study, scent, ambient,
   timedesc, mechanics…), copy-pasteable into a text editor and re-runnable in-game. Round-trips
   a live room to its build-script — the key tool for building the curated fresh copy.
7. **[ROADMAP] Conventions & guides.** A settled, *subtle* ANSI cue palette (preferred, not
   law) + builder guides in-game (`help`) and in `builders-guide.md`. See "Cue convention".

---

## Cue convention [ROADMAP — to settle]
Colour on interactable nouns is the player's breadcrumb, but it's a **guide, not a hard rule** —
whether a builder colours/lists every detail is their call (a richly-cued room teaches itself;
a sparse one rewards `survey`). To settle: a small palette mapping a colour each to *lookable
detail / handleable / studiable zone / hidden-til-revealed* (kept subtle). NOTE: distinct from
the CLAUDE.md §5 **scene-prose** channel colours (narration tone, not interactivity cues).

---

## §0 OOC floor
Zone state is content, not a trap. Reveal/gate conditions **fail open**. `escape`/`forceclear`
relocate the player out of any zone-interior (e.g. a `WombRoom`) and clear facility flags. No
gated detail, hidden exit, or locked seat may ever block the always-available exit.

## What works / what to carry into the fresh build
- ✅ Keep: the zone schema, the look/study/handle/smell/inscribe/survey verb set, `{zone:}`
  tokens with `time_descs`, auto-append-off + colour-cue philosophy, mechanics-on-zones, the
  trigger/reveal_item pattern, body-zones sharing the schema.
- 🔧 Build before/with the fresh copy: `rz export` (#6), the unify pass (#1), the reveal/gate
  generalization (#3), then viewer-aware descs (#2) and senses (#4).
- ✂️ Probably skip: zones-that-remember (#5).
