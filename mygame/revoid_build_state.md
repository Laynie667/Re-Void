# Re:Void — Current Build State
*A sync document for cross-instance coordination*

---

## Purpose

This document captures the exact current state of the Re:Void codebase as of this build session. It is intended to be shared with another Claude instance that has more context on design intent, lore, and vision — so both instances can coordinate without duplicating or contradicting each other's work.

---

## What Has Been Built

### Typeclasses (complete)

| File | Status | Notes |
|---|---|---|
| `typeclasses/accounts.py` | Complete | Wisp identity, consent flags (casual/intimate/mature/bdsm/lead_follow/restraint/**hardcore**), score, visibility, ambient |
| `typeclasses/characters.py` | Complete | 16-layer desc system fields, zone system with types, clothing/wardrobe/outfits, markings, titles (5-part assembly), RP hooks, consent/block, proximity, puppet hooks |
| `typeclasses/rooms.py` | Complete | 17-layer desc assembly, ambient script management, scene state (lock/log/prompt/title/tone/cw), stage overlay, scene details, toggle system, wisp/hub flags, history |
| `typeclasses/scripts.py` | Complete | AmbientScript (randomized interval, pool assembly), SceneTimeoutScript, HousingExpiryScript (stub) |
| `typeclasses/objects.py` | Complete | ObjectParent base |
| `typeclasses/key.py` | **Just built** | Lock key object; holds target_char_id, zone, lock_type (scene/persistent), created_by, created_at; examine shows lock info |
| `typeclasses/written_item.py` | **Just built** | Written document object; holds item_type, content (list), author, sealed flag; read shows content or sealed message |
| `typeclasses/furniture.py` | Stub | Needs full implementation |
| `typeclasses/linked_object.py` | Stub | Needs full implementation |
| `typeclasses/wall_panel.py` | Stub | Needs full implementation |
| `typeclasses/kabeshiri_wall.py` | Stub | Needs full implementation |
| `typeclasses/npc.py` | Stub | Needs full implementation |

---

### Commands (complete)

| File | Status | Notes |
|---|---|---|
| `commands/default_cmdsets.py` | Complete | All command files registered |
| `commands/wisp_commands.py` | Complete + expanded | Full wisp identity suite; **wisp communication commands just added** (see below) |
| `commands/character_commands.py` | Complete | Identity, desc, zones, clothing, wardrobe, outfits, markings, titles, RP hooks, sheet, consent, block, chargen |
| `commands/rp_commands.py` | Complete | say/pose/emote/pmote/whisper/mutter/shout/aside/ooc/tbf/spoof |
| `commands/proximity_commands.py` | Complete | approach/approach/close, withdraw, beside, prox |
| `commands/scene_commands.py` | Complete | scene (start/end/lock/unlock/invite/log/title/prompt/cw/tone/history/status), knock, po (join/leave/skip/next/reset/add/remove) |
| `commands/safety_commands.py` | Complete | safe/safeword (set/info/history), yellow; admin: watch/unwatch/watching |
| `commands/social_commands.py` | Complete | 134 social emotes across 6 consent tiers + CmdPermit |
| `commands/rp_tools_commands.py` | Complete | flock, restrain/unrestrain, lead/unleash, prop/detail/stage/mark |
| `commands/comms_commands.py` | Complete | tell/reply, page, channel (chat/fc), ws (whisper-send), mail |
| `commands/prefs_commands.py` | Complete | dnd, afk, highlight, filter, notify, friends, moodcarry, wispname |
| `commands/chargen.py` | Complete | Character creation flow |
| `commands/freeform_commands.py` | **Not built yet** | See pending section |

---

### Wisp Communication Commands (just added to wisp_commands.py)

These are now live in `commands/wisp_commands.py` and registered in `AccountCmdSet`:

| Command | Aliases | Description |
|---|---|---|
| `wsay <text>` | `"` | Speak from the light. Visible: attributed to mood light. Invisible: sourceless voice. |
| `wpose <text>` | `w:` | Light-based pose. Auto-prepends "The \<mood\> light". |
| `wemote <text>` | `w@` | Freeform pose, no auto-prepend. Visible: mood colored. Invisible: atmospheric dim. |
| `wwhisper <name> = <text>` | — | Targeted whisper. Room sees light lean close. `/page` switch for cross-room. |
| `wmutter <text>` | — | Audible but indistinct. Room hears fragments. |
| `wshout <text>` | — | Carries to adjacent rooms. |
| `wsayverb <verb>` | — | Set wisp speech verb. |
| `wlog on/off/save/clear` | — | Personal scene log for wisps. |

---

### World Modules (complete)

| File | Status | Notes |
|---|---|---|
| `world/pool_loader.py` | Complete | YAML pool loader with cache |
| `world/wisp_visibility.py` | Complete | Wisp visibility rules, room wisp listing, haunting lines |
| `world/gametime.py` | Complete | IC time period, season |
| `world/weather.py` | Complete | Global weather state |
| `world/world_state.py` | Stub | Global IC event flags |
| `world/text_editor.py` | **Just built** | Universal text editor; buffer survives disconnect; targets: setdesc, setbio, setbodylang, setmoodtell, setpresence, setscent, setvoice, settouch, setintimate, wdesc, wsignature, ambient, wambient, zone \<name\>, ambient/zone \<name\>, marking \<#\>, rdesc, rentry, rexamine, rambient |
| `world/freeform_manager.py` | **Not built yet** | See pending section |
| `world/data/pools/wisp/` | Complete | base.yaml, colors.yaml, haunting.yaml |

---

## Decisions Made That Differ from Design Doc v2

These are intentional divergences from the uploaded design documents. The doc has not been updated to reflect them yet.

### 1. `pmote` — Private Pose (not pronoun substitution)

**Doc says:** `pmote <text>` — pose with pronoun substitution (%n %p %o %s)

**What we built:** `pmote <name> = <text>` — private pose

- Caller sees: `[private -> Name] Actor text.`
- Target sees: the full text (mood colored)
- Room sees: nothing

**Reason:** The player explicitly decided pronoun substitution was useless because players write their own pronouns in poses. The private pose pattern was chosen as more useful.

**Action needed from other instance:** Confirm whether private pose is the final design, or whether there's an intended use case for pronoun substitution that wasn't covered. If private pose is final, the doc should be updated.

### 2. `ooc` command lives in rp_commands.py (not wisp_commands.py)

The `ooc` command handles two cases:
- `ooc <text>` — in-scene OOC comment (bracketed)
- `ooc` (no args) — return to wisp state (unpuppet)

This means the same command key handles both in CharacterCmdSet. The wisp_commands.py still has its own CmdOOC for the AccountCmdSet so wisps don't accidentally double-fire.

### 3. OOC transition prose

**Doc (implicit):** Not specified.

**What we have:**
```
Witch steps back — the edges of them soften,
the specific giving way to light.

[ wisp: Witch | mood: uncertain ]
Witch remains in The Velvet Room.
Type 'ic Witch' to return.
```

**Status:** Placeholder prose. Player wants to write lore-accurate transition text. Awaiting lore input.

### 4. `hardcore` flag added to consent system

Added `"hardcore": False` to the consent flags dict in accounts.py. Required for `plock` (persistent locks). Was missing from the original accounts.py implementation.

---

## What Is Still Pending

Listed in build priority order:

### High Priority (blocking other systems)

1. **`world/freeform_manager.py`** — prop/stage/extra/env/lock storage utilities
2. **`commands/freeform_commands.py`** — the full freeform suite (place, stage, extra, slock, plock, write, sound, scent, light, etc.)
3. **Character `return_appearance`** — `look <character>` currently uses Evennia's default; needs the 16-layer assembly

### Medium Priority

4. **Builder commands** — `rdesc`, `rtime`, `rweather`, `rambient`, `toggle` (player-facing), etc. Rooms can't be populated without these.
5. **Relationship system** — `rel list`, `rel show`, `rel memory`, `rel desc`, `rel stage`
6. **Reputation/faction commands** — `rep give`, `rep list`, `faction list`, `faction apply`
7. **Language system** — `lang`, `lang speak`, `lang list`

### Lower Priority

8. **Position/furniture system** — `sit`, `kneel`, `lie`, `stand`; furniture typeclass
9. **Linked object architecture** — wall panel, kabeshiri, leash/collar
10. **Household system**
11. **Immersion systems** — dishevelment, intoxication, photograph, scent trail, corridor overhear, etc.

### Needs Lore/Narrative Input Before Building

12. **The Forming** — `world/at_initial_setup.py` and tutorial rooms. The mechanics are ready to build once we know: what rooms the space needs, what lore text it carries, what systems it needs to walk players through, and what can be left to organic discovery.
13. **OOC transition prose** — the text shown when `ooc` (no args) is typed to return to wisp state. Placeholder currently in place.

---

## Architecture Notes for the Other Instance

A few things that may not be obvious from the design doc:

**Evennia 4.x puppet hooks take no arguments.** `at_pre_unpuppet()` and `at_post_puppet()` on Character are called with no positional args. The account is retrieved via `self.account` on the character. This was a source of several bugs that are now fixed.

**`at_post_unpuppet` on Account is overridden** to suppress Evennia's default OOC screen, which would otherwise appear every time `ooc` is typed. Our CmdOOC handles its own output.

**Freeform props are NOT Evennia objects** — they're stored in `room.db.freeform_props` as a dict. Same for stage overlays (`room.db.stage_overlays`), extras (`room.db.freeform_extras`), and environmental modifications (`room.db.env_scent`, `room.db.env_light`, `room.db.env_sounds`). The architecture notes in `revoid_freeform_system.md` define the exact storage structure.

**The text editor (`world/text_editor.py`)** uses a separate `EditorCmdSet` with priority 200 that replaces normal commands while active. Buffer is stored on `caller.db._editor_buffer`. The editor survives disconnect.

**Consent flags** are checked at two levels: account-level (`account.db.consent_flags`) and character-level. Character flags take precedence; account flags are fallback. The current flags are: casual (default on), intimate, mature, bdsm, lead_follow, restraint, hardcore.
