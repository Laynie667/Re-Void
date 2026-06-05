# The Facility — Systems Catalogue

A survey of **every** system that makes the facility/realm run: its purpose, key
functions, the mechanics it owns, where it overlaps others (redundancies), and where
it could improve. Companion to `FACILITY_AUDIT.md` (which tracks bugs/conflicts). For
your review. Maintained by the build loop.

Legend: **fn** = function/method · **st** = db state it owns · ⚠ = redundancy/overlap ·
→ = improvement idea.

---

## 1. Realm & world  (`world/realm_build.py`)
- **Purpose:** dig the disconnected grid realm, furnish it, gate entry/return, tear it down.
- **fn:** `build_realm` (full dig), `facility_upgrade` (in-place idempotent migration — adds
  missing rooms/exits/placards/album/office-anatomy), `teardown_realm`, `escape` (OOC floor:
  home+purge), `force_clear` (bulletproof per-attr reset), `reveal_return` (gate the way home),
  `_furnish` (zones/tokens/mechanics/furniture/NPCs/placard), `_install_mechanic`.
- **st:** `db.realm` (rooms/words/return_wp), area tags, `_REALM_TAG`.
- **Data:** `_ROOMS` (13), `_EXITS`, `_ROOM_ZONES`, `_ROOM_FURNITURE`, `_ROOM_NPCS`,
  `_ROOM_MECHANICS`, `_ROOM_AMBIENT`, all the NPC trigger trees.
- ⚠ **Two reset paths:** `force_clear` here and `run_facility_reset` in `facility_build.py`
  must be kept in lockstep — every new persistent attr has to be added to both. Real
  maintenance burden and the single biggest source of "forgot to clear X" risk.
  → Extract a single `FACILITY_STATE` spec (attr → default) both paths consume.

## 2. The cycle  (`typeclasses/facility_script.py` · `RealmCycleScript`)
- **Purpose:** the phase machine that drags her room-to-room and runs each room's scene.
- **fn:** `at_repeat` (drive), `_choose_destination` (handler-weighted next room),
  `_drag` (relocate + narrate), `_mature_get` (lineage), and the phase scenes: `_do_milk`,
  `_dose`, `_procedure`, `_pen_breed`, `_hypno`, `_dairy`, `_toilet`, `_sty`, `_showroom`,
  `_office`, `_deepstock`, `_nurse`, `_parlour`, plus `_grow_udder`, `_made_to_beg`,
  `_devote`, `_impose_clause`, `_sell`, `_demote_staff`, `_facility_event`.
- **st:** `phase_index`, `orifice_zone`.
- **Phases:** milk / breed / condition / display / toilet / punish / show / owned / mark /
  deep / nurse. **NPCs:** `FacilityAttendant`, `FacilityBeast`, `FacilityScion`.
- → `_choose_destination` weights are inline magic numbers; a small table would be tunable.
- → The base `FacilityScript` (single-room rig) and `RealmCycleScript` share huge pools —
  fine, but the single-room path is now largely superseded by the realm. ⚠ possible to retire.

## 3. Conditioning  (`world/conditioning.py`)
- **Purpose:** the brokenness meter + staged threshold effects.
- **fn:** `add_conditioning` (suggestibility-scaled), `deepen_on_climax`, `_apply_thresholds`,
  `get/_refresh` stage. **st:** `conditioning`, `conditioning_applied`. 9 thresholds
  (floor→speech→trigger→designation→name→permanent→doll→identity→lockself→imprint).

## 4. Binding effects  (`world/binding_effects.py`)
- **Purpose:** the central effect engine items/contracts/collars fire.
- **fn:** `apply_effects` / `remove_effects` (~30 effect keys), `install_trigger` +
  `_check_installed_triggers` + the `_inst_*` response handlers (kneel/beg/orgasm/blank/
  obey/freeze/leak/recite), `passive_tick` (stim + posture, ridden by the milk-gland script),
  `check_say_allowed`/`check_trigger`/`check_navigation_allowed`/`check_anti_clothing`.
- **Effect keys:** auto_consent, lock_navigation/self_cmds/self_remove, block_endcycle,
  orgasm_denial, continuous_stimulation, arousal_floor, forced_posture, exhibition,
  anti_clothing, broadcast_sensation, speech_filter, install_triggers, conditioning_on_wear,
  suggestibility, lactation_primer, forfeit_name, lock_conditioning, breeding_quota,
  required_honorific, compliance_threshold, milk_quota, cum_receptacle, mark_signed,
  realm_cycle, body_processing, perpetual_heat, pet_triggers, animal_sleeve.

## 5. Breeding, holes, marks  (`world/gang_breeding.py`)
- **fn:** `gang_inseminate` (deposit + quota + lineage), `record_use`/`add_gape`/
  `hole_capabilities`/`gape_word` (hole training), `record_mark` (freeform + board),
  `add_piercing` (real `PiercingItem`), `make_animal_sleeve`/`scent_mark`/`mucus_plug`/
  `apply_filth`/`clear_animal_sleeve`, `_birth_offspring` (spawns get; `FacilityScion` for
  the bethany line), `animal_holes`, quota helpers.
- ⚠ **Marks stored twice:** `db.facility_brands` (legacy strings) *and* real freeform items
  (`FreeformManager`). `record_mark` writes both; `board` reads facility_brands, `marks`
  reads freeform. → Pick freeform as canonical; keep facility_brands as a thin cache or drop.
- ⚠ **`offspring_progress` (legacy abstract counter)** coexists with the real pregnancy
  system; `_maybe_offspring` is now a fallback, and the BROOD drug still bumps the old
  counter. → Retire `offspring_progress`/`_maybe_offspring` once pregnancy is confirmed stable.

## 6. Pregnancy & lineage  (`world/pregnancy.py`)
- **fn:** `is_fertile`/`is_pregnant`, `on_bred`, `conceive`, `accelerate`, `gestation_tick`
  (belly stages), `deliver` (litter via `_birth_offspring` + quota raise + lactation), `clear`.
- **st:** `pregnancy`, `cycle_day`, `belly_desc_backup`, `pregnancy_belly`. Litter sizes per
  species incl. `bethany`. ⚠ belly desc backup is its own dict (see §13 zone-backup overlap).

## 7. Compliance & punishment  (`world/compliance.py`)
- **fn:** `register_defiance` (docility-suppressed), `punish`, `register_compliance` +
  `_grant_climax` (the relief leash), `check_earn_back`, `forfeit_freedom`,
  `penalize_quota_shortfall`. **st:** defiance, compliance_streak, freedom_forfeited,
  compliance_threshold.

## 8. Factions / grade / title  (`world/factions.py`)
- **fn:** `add_standing`, `get_facility_tier`, `_apply_facility_title` (ownership-wins),
  `seed_facility_title`. **st:** `db.factions`, title slots, `facility_grade`,
  `facility_owner`. 6 grade tiers. ⚠ title suffix written by grade/sale/ownership — resolved
  by the ownership-wins rule.

## 9. The mind  (`typeclasses/mind_state_item.py`)
- **fn:** `render` (the read-out), `compute_docility`, `tick` (withdrawal/craving/drift),
  `refresh`, `find_mind_item`. Installed on a real `mind` zone.
- ⚠ **State-view overlap** with the `board` command and `FacilityBoard` furniture. Now
  intentional/tiered: `board` = staff dossier (canonical, full), mind zone = in-world body
  read-out (`look <her> mind`), board furniture = the wall rendering of `board`. Documented,
  not accidental — but worth keeping deliberately in sync.

## 10. Body systems  (engaged, not owned by the facility)
- **Production** (`production_item.py`, milk glands), **WombRoom** (flood/seal/meat-toilet),
  **Inflation** (cumflation/capacity), **BodyMod** (breast/penis size, `_grow_udder`),
  **arousal_script** (floor + climax), **heat_script** (perpetual heat), **GlobalFluidBank**.
  Installed by `facility_build.provision_body` on signing; tracked on `db.facility_items`.

## 11. Facility implants  (`typeclasses/facility_implants.py`)
- `MilkPortItem` (nipple zone + duct + force-feed inflation), `GaugeRingItem` (one-way
  membrane), `CowRingSet` (heavy cow piercings), `BethanyCollar` (owned collar). Each creates
  its own default zone where needed; tracked for teardown; item-created zones in
  `db.facility_created_zones`.

## 12. Bethany  (`typeclasses/bethany_script.py`)
- **fn:** `provision_bethany` (multicock + cum/piss production), `BethanyScript` (chance
  visits, room-aware, gates the cycle via `bethany_busy`, climax deposits + breeds every hole
  + `bethany_deposit_effect` laced devotion), `_spawn`/`_mark_owned`. Office Bethany is a
  static NPC; visit Bethany is spawned/despawned. ⚠ possible to have 2–3 Bethanys in one room
  momentarily (see AUDIT).

## 13. Intake  (`typeclasses/intake_script.py`)
- The lobby driver: the screen subliminal squeeze, dawdle-worsens-contract, suggestibility
  trigger, idle forced-sign, the door opening on signing.

## 14. Commands  (`commands/facility_commands.py`)
- `board`/`quota` (the dossier — now canonical), `process` (the witness/staff verb: ~25
  actions), `facilityreset` (`/force`,`/purge` — the OOC floor command), `standing`, and the
  agency verbs `present`/`beg`/`thank`/`submit`/`struggle`/`mount`. **Furniture:**
  `FacilityFurniture`/`FacilityBoard`/`FacilityPortfolio`.

## 15. Content data (deep pools)
- **Drugs (14):** swell, yield, sensitize, capacity, brood, compliance, bimbo, dependence,
  estrus, lactation, solvent, cumslut, forget, devotion.
- **Procedures (15):** pierce, brand, stim_implant, ring_fit, milk_port, tail, fertility_
  implant, tongue, womb_tattoo, clit_hood, latex, udder, rings, cowset, oneway.
- **Events (10):** inspection, open_house, culling, audit, buyer, restock, breeding_demo,
  conditioning_broadcast, hose_drill, milking_parade.
- **Contract:** 14 visible + 29 hidden clauses (`facility_build`) + Bethany's 6 personal
  clauses. **Scene pools:** dozens, 3–6 variants each, brace-scanned safe.

---

## Cross-system redundancies (catalogued)
1. ⚠→✅ **Two reset paths** (`force_clear` / `run_facility_reset`) — **mitigated.** New
   `world/facility_state.py` (`FACILITY_FLAGS`, 86 flat flags, + `apply_reset_flags()`) is the
   single source of truth; both paths now call it (after consuming the name/title backups), so
   a new flag added to the spec is cleared by both automatically. The old per-attr loops remain
   as belt-and-suspenders and can be trimmed later. Also addresses redundancy #6. *(§1)*
2. ⚠ **Marks stored twice** (`facility_brands` strings + freeform items). *(§5)*
3. ⚠ **`offspring_progress` legacy** vs the real pregnancy system. *(§5/§6)*
4. ⚠ **Three state-views** (`board` / mind zone / board furniture) — now tiered & deliberate. *(§9)*
5. ⚠ **Zone-desc backups per-system** (sleeve / belly / item `prev_nude`) — different zones
   today, but three mechanisms doing one job. *(§6/§11)*
6. ⚠ **~60 flat `db.*` flags** — no namespace; ties into reset-sync risk. *(§1)*
7. ⚠ **Single-room `FacilityScript`** largely superseded by the realm cycle. *(§2)*

## Improvement backlog (by payoff)
- ✅ **DONE — unify the two reset paths** behind one spec (`world/facility_state.py`). Kills
  redundancies 1 & 6 and the "forgot to clear X" class. *Next on this thread:* retire the now-
  redundant per-attr clear loops in both paths (safe once the spec is confirmed live), then
  retire `offspring_progress` (3).
- **Medium:** make freeform the canonical mark store, `facility_brands` a derived cache (2).
  Unify zone-desc backups behind one helper (5).
- **Low / polish:** dedupe Bethany NPCs (AUDIT); table-drive `_choose_destination` weights;
  per-NPC `rp_name` aliasing; retire the single-room rig if unused (7).

---

# PART B — the wider game (non-facility systems)

A survey of the ~45 command modules + core typeclasses outside the facility, grouped by
area, with overlap/improvement notes. (Inventoried by size + module purpose.)

## B1. Character & identity
- `character_commands.py` (4.4k lines — the biggest module: name/desc/outfit/wardrobe/mood/
  voice/scent/title/sheet/consent/block, wear/remove/insert), `chargen.py`, `bio_commands.py`,
  `prefs_commands.py`. → The size of `character_commands` suggests it could be split by concern
  (appearance vs outfit vs identity vs consent) for maintainability.

## B2. Roleplay & speech
- `rp_commands.py` (say/pose/emote/look/whisper/mutter/aside/ooc/shout + consent-gated speech),
  `social_commands.py` (the directed social/intimate emote table), `scene_commands.py`,
  `rp_tools_commands.py`, `comms_commands.py` (tell/page/reply/channels), `proximity_commands.py`
  (approach/withdraw/beside/aside/prox). ⚠ **`aside` collision** (rp vs proximity — see AUDIT
  §1d). ⚠ speech verbs also exist in `wisp_commands.py` for the wisp state (intentional split).

## B3. Zones, body & intimacy
- `roomzone_commands.py` + `zone_interact_commands.py` + `interact_commands.py` (zone look/
  study/handle), `freeform_commands.py` (freeform marks/placement), `body_mod_commands.py`
  (breast/penis/testicle mods), `penetration_commands.py`, `womb_commands.py`,
  `inflate_commands.py`, `restrain_commands.py`, `mechanic_commands.py` (install zone mechanics),
  `shower_commands.py` (cursed shower), `dairy_commands.py`. → Several overlap the facility's
  installs; the facility reuses these real systems (good — not redundant).

## B4. World, navigation & housing
- `housing_commands.py`, `door_commands.py`, `stair_commands.py`, `teleport_commands.py`,
  `waystone_commands.py` (+ the realm's waystone/waypost). ⚠ **`knock` collision** (door vs
  scene — see AUDIT §1d). ✅ waystone/waypost no-key bugs fixed (AUDIT §1c).

## B5. NPCs, furniture, props, minigames
- `npc_commands.py` (ask/greet/nservice/triggers — the system the facility NPCs use),
  `furniture_commands.py`, `rocking_horse_commands.py`, `jacuzzi_commands.py`,
  `cah_commands.py` (cards-against-humanity minigame), `cooking_commands.py`,
  `economy_commands.py`, `item_commands.py`, `ogram_commands.py`, `rel_commands.py`
  (relationships), `safety_commands.py` (watch/block — `watch/list` bug fixed, AUDIT §1b),
  `cycle_commands.py` (the endcycle/struggle verbs).

## B6. Core typeclasses (non-facility)
- `characters.py` (zones, appearance layers, rp_name→alias sync — added this loop),
  `rooms.py` (15-layer appearance incl. wisps), `npc.py` (tiered NPC + triggers),
  `objects.py`, `exits.py`, `scripts.py` (PassiveAccumulationScript — drives production +
  the facility passive_tick), plus the body items (`production_item`, `womb_room`,
  `inflation_item`, `body_mod_item`, `piercing_item`, `wearable_item`, `collar_item`,
  `arousal_script`, `heat_script`, `fluid_bank`).

## B7. Non-facility improvement notes
- → **Split `character_commands.py`** (4.4k lines) along concern lines.
- → **Resolve the two cmdset collisions** (`aside`, `knock`) — ✅ done (AUDIT §1d); two now-
  dead classes left to delete whenever (AUDIT §0a).
- → **Centralise duplicated name-helpers** — `_char_name`/`_char`/`_name`/`_mood_color`/
  `_find_character` are copy-pasted across 2–5 modules each. One `commands/_helpers.py` would
  DRY them. (AUDIT §0a)
- → **Per-NPC `rp_name` alias** (the PC fix applied to NPCs) so `ask`/targeting is robust.
- → Many `except Exception as e:` where `e` is only logged — fine, but a project-wide
  logging convention would make failures easier to trace.
- ✅ No-key `search_object`, `hasattr`-account, bare `except:`, mutable defaults, stray-brace
  `.format`, unguarded `[0]`/`int()` — all swept clean game-wide (see AUDIT).
- ✅ **`print()` audit:** all 56 are in `world/` build/migration/loader scripts (run via `@py`
  by staff, where console output is intended) — **none in live command/typeclass paths.** Not
  a bug. (Could route through Evennia's logger for consistency, but low value.)

*Loop pass 13: created this catalogue; made `board` the canonical full dossier.*
*Loop pass 14: extended the catalogue to the wider game (Part B — ~45 command modules + core
typeclasses, grouped by area); flagged two real `CharacterCmdSet` key collisions (`aside`,
`knock`) for your decision (AUDIT §1d).*
