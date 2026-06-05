# The Facility — Audit, Conflicts, Bugs & Improvements

A living review of the realm/facility systems for **your** review. Maintained by the
build loop. Severity: 🔴 bug/conflict · 🟡 risk/inconsistency · 🟢 improvement idea.
Items get struck through / moved to "Resolved" as they're fixed.

---

## 0. Operational note (read first)

- 🟡 **Re-run `build_realm(me)` to get new rooms.** Rooms added after your last build
  (Showroom, Deep Stock, Nursery, Bethany's Office) won't exist in an already-built
  realm until you rebuild. The cycle guards missing rooms (`if "office" in avail`), so
  an old realm won't crash — it just won't route to the new rooms. `teardown_realm` then
  `build_realm` is the clean path; `force_clear`/`escape` remain the OOC floor.
- 🟡 **The rp_name → alias fix only applies on next login** for already-puppeted
  characters (`at_post_puppet`). If page/tell/emote still can't find someone mid-session,
  they should relog once (or `setname <same name>`).

---

## 1. Conflicts

- 🟡 **Title-suffix stomping.** Three systems write `db.title_suffix`: the faction grade
  (`factions._apply_facility_title`), the sale (`_sell` / `process buy`), and Bethany's
  ownership (`_devote`/`_mark_owned`). They all share one backup (`facility_title_backup`,
  guarded so the *true* original is preserved), but they overwrite each other *live* — so
  a standing-up grade tick can replace "— Bethany's" with "— Broodmare" until the next
  ownership beat re-stamps it. *Fix idea:* an ownership-wins rule (if `bethany_owned` or
  `facility_owner`, the grade system skips the suffix), or a priority field.
- 🟡 **Installed-trigger phrases overlap staff dialogue.** `_check_installed_triggers`
  fires for ANY speaker, and some NPC trees contain words that are also common trigger
  phrases ("good girl", "present", "heel"). `ask`-ing a staffer could incidentally fire
  the player's drop. This is *mostly intentional* (the staff weaponise her conditioning),
  but worth a deliberate decision — maybe NPC `say` from trees shouldn't auto-fire, only
  free-typed speech. *Fix idea:* a `from_trigger_safe` flag on NPC trigger output.
- 🟢 **Zone-desc backups are per-system.** `sleeve_desc_backup`, `belly_desc_backup`, and
  the latex/milk-port nude rewrites each back up independently. They target *different*
  zones today (pussy/anus/mouth vs belly vs nipples), so no live conflict — but if two
  ever target the same zone, restore order would matter. *Fix idea:* one unified
  `db.facility_zone_backup` keyed by zone, written through a single helper.

## 2. Bugs

- 🔴→✅ **Office Bethany had no anatomy.** `provision_bethany` was only called for the
  *spawned* visit-Bethany, so the static office Bethany showed no cock on `look` and her
  office breeding never engaged a real penetrator. **Fixed this pass** (provision on
  furnish + `_office` now penetrates with the room's Bethany).
- 🟡 **Duplicate Bethany NPCs.** Intake Bethany + office Bethany are two persistent NPCs,
  and a visit spawns a third transient one. In a room with two, `ask Bethany` / targeting
  multimatches. *Fix idea:* the roaming visit should reuse a single canonical Bethany
  (move her in) rather than spawn, or tag the office/intake ones distinctly.
- 🟡 **`bethany`-line get spawn as `FacilityBeast`.** Her offspring are flavoured "futa
  daughter" but instantiated as animal beasts (so `_provision_beast` gives them a generic
  animal cock if they ever breed her). *Fix idea:* a small `FacilityScion` typeclass (futa
  attendant w/ a Bethany-style cock) for `species == "bethany"`.
- 🟡 **Demoting a key staffer removes a cycle voice.** `_demote_staff` can demote the
  handler/stockman; the demoted NPC keeps its trigger tree (so `ask` still works) but
  `_drag`'s handler-attribution and `_choose_destination`'s flavour lose their actor.
  Low impact; *fix idea:* protect role-critical NPCs, or respawn a replacement.

## 3. Improvements — character mechanics

- 🟢 **rp_name aliases for NPCs too.** Players will `process the handler` / `kiss bethany`;
  NPC keys already mostly match display names, but syncing `rp_name` → alias on facility
  NPCs (like we now do for PCs) would make every target robust.
- 🟢 **Namespace the facility state.** There are ~60 `db.*` flags now. A single
  `db.facility = {...}` dict (with helpers) would make teardown a one-liner and reduce the
  risk of a new attribute being forgotten in a reset path. Big refactor; high payoff.
- 🟢 **A `forgotten` readout.** `db.facility_forgotten` logs what FORGET took; surface it
  (on the mind monitor, or a staff-only `process <her> inspect`) so the loss is legible.
- 🟢 **Gape/capability surfaced on the sheet.** Hole capabilities (knot/double/fist/
  prolapse) and permanent gape drive scenes but aren't shown anywhere the player reads.
  A discreet body-state line would pay off the training.

## 4. Improvements — room / world mechanics

- 🟢 **Zone-token budget on big rooms.** `_furnish` tokenises *every* zone into the room
  desc, so rooms with many zones (Office, Pens) produce a long `look`. Consider a curated
  "featured zones" subset for the inline render, leaving the rest to `look <zone>`.
- 🟢 **Ambient cadence.** Room `ambient_msgs` exist but I haven't confirmed a driver fires
  them on a timer in the realm rooms (vs only the cycle beats). Worth verifying an ambient
  ticker runs so empty-room atmosphere lands between cycle phases.
- 🟢 **Witness discoverability.** `process <her> <action>` is powerful but undiscoverable;
  a board/sign in each room ("STAFF: process this unit — breed/milk/dose/…") would teach
  other players the verb in-fiction.
- 🟢 **Exit flavour.** Realm exits are auto-named from room keys; bespoke exit names/descs
  ("DOWN — Sub-Level P", a sealed hatch) would sell the geography.

## 5. OOC floor — verification checklist (keep current)

Every persistent thing the facility installs must be undone by `force_clear` / `escape` /
`run_facility_reset(purge)`. Confirmed-covered: conditioning, suggestibility, docility,
dependence, cravings, perpetual heat, lactation lock, speech filters, installed triggers,
designation/name, title slots (+ ownership/grade), consent (facility + binding backups),
piercings (facility-tagged), freeform marks, body installs (glands/womb/breast/inflation/
mind monitor + item-created zones), animal-sleeve descs + barriers, pregnancy/belly/cycle,
offspring roster + spawned get, sale/owner, latex, bethany devotion/brand, FORGET log,
realm scripts (realm_cycle/heat/bethany_visit/milking). **When adding ANY new persistent
state, add it here and to all three reset paths.**

---

*Last build-loop pass added: office-Bethany anatomy fix, FORGET + DEVOTION drugs + the
devotion-withdrawal ache, the flared+knotted multicock, employees-as-stock (`demote`).*
