# Game-Wide Improvement Audit

*A standing, prioritized list of improvements across all of Re:Void — not just the
Facility. Maintained alongside FACILITY_SYSTEMS_CATALOGUE.md / FACILITY_AUDIT.md.
Items marked ✅ were done in the recent build pass; ☐ are open. Each names the real
file(s) so the work is actionable, not vague.*

---

## 0. Principles (apply to every item)

- **Real, not faked** — route through the actual subsystem (FreeformManager, gang_breeding,
  binding_effects, pregnancy, …); never store a parallel string when a real item/record exists.
- **OOC floor stays sacred** — `escape`/`force_clear`/`facilityreset` always free, never gated;
  any new persistent flag goes in `world/facility_state.FACILITY_FLAGS`.
- **No immersion-breaking gating** — keep dread in-fiction; the only hard exit is the floor.

---

## 1. Recently shipped (this build arc) ✅

- ✅ Named-sire lineage end-to-end (`gang_breeding` + `pregnancy`): get records its individual
  sire; `studbook` command + ledger board render it.
- ✅ Offspring gender incl. **futanari** (`offspring_sex`/`can_sire`); futa & sons sire, females
  are broodstock; neutered retired from siring.
- ✅ **Neuter & sissify** male stock (`_proc_neuter`/`_proc_sissify`, `sissy` filter).
- ✅ Matured get → **named studs** that breed the dam by name (`_mature_get`/`present_stud`).
- ✅ Star economy fills from every source incl. **milk quota** (`_log_milk`).
- ✅ World **inhabited** — present studs in the Pens + other-stock ambient across all cycle/
  showroom/nursery/deepstock/gallery rooms.
- ✅ Regression / Little Box / 5 little-clauses / Bethany seat & nugget-animal scenes.
- ✅ **Trigger matching** now punctuation-tolerant (`_check_installed_triggers`) — fixes ALL
  installed triggers game-wide, not just facility.

---

## 2. Whole-game cleanups (known redundancies / sharp edges)

- ✅ **Unify the orgasm-denial flags.** (world/arousal_rules.py) Three flags interact across files —
  `orgasm_denial` / `orgasm_denial_lifted` / `rule_come_permit` (`typeclasses/arousal_script.py`
  caps at 99; `world/compliance._grant_climax`, `world/rules.enforce`, `world/conditioning.
  deepen_on_climax`, `world/star_chart`, `commands/facility_commands` all touch them). Propose a
  single `world/arousal_rules.py` resolver: `may_climax(char) -> (bool, reason)` and
  `consume_permit(char)`, called from one place in arousal_script. Reduces the "permitted but
  still capped / punished a granted release" class of bug. *Needs careful standalone tests.*
- ✅ **Collapse double-stored marks.** (record_mark single-writes freeform; facility_mark_texts reads) `db.facility_brands` (legacy strings) duplicates real
  freeform items (`record_mark`). Readers: `facility_script`, `facility_commands`, `realm_build`,
  `facility_build`. Make `facility_brands` a pure read-through of freeform marks (or drop it and
  point all readers at `FreeformManager`), so `marks`/`brands`/`look` never disagree. Keep the
  flag in FACILITY_FLAGS until all readers move.
- ☐ **Speech-filter order contract.** `little_talk`/`stuffed`/`sissy`/`baby_talk` stack; document
  and enforce a canonical apply-order in `world/speech_filters.apply_speech_filters` (right now
  it's list-order dependent) so combinations read consistently.
- ✅ **Quota shape drift.** (gang_breeding.quota_pair / ensure_quota_entry) `breeding_quota` is sometimes `{sp:int}`, sometimes
  `{sp:{current,required,…}}` (noted in code as a `_SaverDict`). Add one `quota_entry(q, sp)`
  normalizer in `gang_breeding` and route all readers through it.

## 3. Facility — deeper still (open)

- ☐ **Dairy procedures**: engorgement/relief loop tied to the milk clause — left unmilked past a
  threshold, arousal + ache climb until relief is *granted* (the relief becomes the leash).
  Reuse `production_item` + `arousal_script`; pair with the Tithe-of-Milk clause idea.
- ✅ **Named fellow-resident** with continuity (`world/facility_fellow.py`) — a recurring unit (or two) the cycle places in
  rooms, with their own slowly-progressing state, so the world has faces, not only ambient shapes.
  Reuse `FacilityScion`/`NPC`; keep them realm-tagged.
- ☐ **Procedure breadth**: clit-pump/permanent-gape devices, real branding *iron item* (vs the
  current mark string), tongue-split as a speech effect, corset/waist-training body-processing.
- ☐ **The other branches**: the hub realm + the cabin realm are still thin (per post_office
  backlog) — give them the same inhabited-world + real-systems treatment.
- ☐ **Maze instances**: place the built `MazeRoom` for real (facility "hall after intake";
  forest in the hub) + the Vesper map item (`design/post_office.md` backlog).

## 4. Cross-game systems (outside the facility)

- ☐ **Relationships/reputation** (`world/relationships.py`, `world/reputation.py`,
  `world/factions.py`) — three adjacent standing systems; audit for overlap and a shared
  "standing track" primitive.
- ☐ **Consent layer surfacing** (`world/consent.py` + `consent_commands`) — make the
  consent/rules/contract stack legible to players from one command (`consent` already exists;
  extend to show active rules + contract clauses + the floor reminder in one view).
- ☐ **Crafting/economy** (`crafting_templates`, `economy`, `wallet`, `item_loader`) — confirm the
  facility scrip (`facility_credits`/`economy`) and the general `wallet` don't silently diverge.
- ☐ **Weather/gametime/wisps** (`weather`, `gametime`, `wisp_visibility`) — ambient world systems;
  verify the realm (disconnected grid) degrades gracefully when these don't apply.
- ☐ **Test coverage**: `world/test_build.py` / `test_reset.py` are the de-facto integration tests.
  Add cases for the new systems (regression, clauses, lineage gender/sire, neuter/sissify) so the
  OOC-floor guarantee is regression-tested, not just hand-verified.

## 5. Prose / RP texture (ongoing)

- ✅ Deepened the thin high-frequency pools: `_PROCESS_VOICE` 14→22; lobby/holding/parlour/office
  ambient to 7–8 each. (Per-phase beat pools could still grow further.)
- ✅ **Per-sire voice** (`world/facility_animals.sire_beat` + temperaments) — Caesar/Sultan/etc.
  breed with distinct character; promoted get-studs get a temperament too.
- ✅ A single composed `state` read-out (aliases `status`/`self`) now ties the self-knowledge
  family together — mind/headspace/body/line/stars/quota/clauses/standing in one page, each
  pointing at its detail command, always ending on the floor reminder.
