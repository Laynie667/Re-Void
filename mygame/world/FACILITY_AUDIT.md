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

- 🟡→✅ **Title-suffix stomping.** The faction grade, the sale, and Bethany's ownership all
  wrote `db.title_suffix` and overwrote each other live (a grade tick could replace "—
  Bethany's"). **Fixed:** `_apply_facility_title` now applies an **ownership-wins** rule —
  if `bethany_owned`/`facility_owner` is set, the grade keeps the faction slot but won't
  overwrite an owner suffix.
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

## 1b. Codebase-wide sweep (beyond the facility)

- 🔴→✅ **`watch/list` always empty (2 sites).** `safety_commands.py` `CmdWatch._list`
  and the admin watch-list both scanned `search_object(typeclass="…Character")` with no
  key — the same `[]` gotcha — so the watch list always reported "not watching anyone."
  **Fixed:** both now use `Character.objects.all()`.
- 🟢 **By-name searches now resolve display names for free.** `economy_commands`,
  `ogram_commands`, `wisp_commands`, `scripts.py` search by `name`+typeclass (the *working*
  pattern) — and since `rp_name` is now registered as an alias (login sync), those resolve
  a character's display name too. No change needed; noted as a dependency on the alias fix.
- ✅ **Whole `mygame/{typeclasses,commands,world}` tree compiles clean** (py_compile sweep).
- 🟡 **Remaining gotcha audit:** all other `search_object(...)` calls reviewed pass a key
  positional (waystone/waypost/womb dbref lookups, char-by-name) — none hit the no-key `[]`
  trap. The waystone/waypost ones were already corrected to `.objects.all()` in earlier work.
- ✅ **Stray-brace `.format()` crash class ruled out.** AST-scanned all ten pool/scene files
  for any `{…}` token in a string that's later `.format(t=t)`-ed; the only hit is the
  intentional `{zone:%s}` (`%`-format) template. No pool string can throw `KeyError`/
  `ValueError` at runtime. Each multi-token pool (`{who}`/`{price}`/`{owner}`/`{cup}`/
  `{phrase}`) is only ever `.format`-ed by a caller that supplies those keys.

## 2. Bugs

- 🔴→✅ **Office Bethany had no anatomy.** `provision_bethany` was only called for the
  *spawned* visit-Bethany, so the static office Bethany showed no cock on `look` and her
  office breeding never engaged a real penetrator. **Fixed this pass** (provision on
  furnish + `_office` now penetrates with the room's Bethany).
- 🟡 **Duplicate Bethany NPCs.** Intake Bethany + office Bethany are two persistent NPCs,
  and a visit spawns a third transient one. In a room with two, `ask Bethany` / targeting
  multimatches. *Fix idea:* the roaming visit should reuse a single canonical Bethany
  (move her in) rather than spawn, or tag the office/intake ones distinctly.
- 🟡→✅ **`bethany`-line get spawn as `FacilityBeast`.** **Fixed:** new `FacilityScion`
  typeclass (futa get, knotted flare-tipped cock) is used for `species == "bethany"`, and
  `_provision_beast` now gives scions a real futa cock + knot — so her own line breeds her
  back as futa, not animals.
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
- 🟢→✅ **A `forgotten` readout.** **Done:** the mind monitor now shows the FORGET log
  (last 5 redacted items), plus owner/devotion/personal-clauses and the lineage (offspring
  counts + the incest-loop note). `look <her> mind` reads the whole damage now.
- 🟢→✅ **Gape/capability surfaced.** **Done:** the monitor now prints a trained-holes line
  per hole (gape word + what it can take: knot/double/fist/prolapse).

## 4. Improvements — room / world mechanics

- 🟢 **Zone-token budget on big rooms.** `_furnish` tokenises *every* zone into the room
  desc, so rooms with many zones (Office, Pens) produce a long `look`. Consider a curated
  "featured zones" subset for the inline render, leaving the rest to `look <zone>`.
- 🟢 **Ambient cadence.** Room `ambient_msgs` exist but I haven't confirmed a driver fires
  them on a timer in the realm rooms (vs only the cycle beats). Worth verifying an ambient
  ticker runs so empty-room atmosphere lands between cycle phases.
- 🟢→✅ **Witness discoverability.** **Done:** every realm room now gets a "staff handling
  placard" (FacilityFurniture) listing the full `process <unit> <action>` verb set
  (incl. appraise/buy/demote) in-fiction, so visiting players learn how to use the stock.
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

*Loop pass 1: office-Bethany anatomy fix, FORGET + DEVOTION drugs + the devotion-withdrawal
ache, the flared+knotted multicock, employees-as-stock (`demote`).*
*Loop pass 2: title-suffix ownership-wins fix, `FacilityScion` (futa get), and Bethany's
bespoke personal clauses (honorific/name/collar/crave/display/line — each a real enforced
term, imposed one at a time in the office, logged + reset-safe).*
*Loop pass 3 (autonomous): in-fiction `process`-verb signage in every room (witness
discoverability), and the office "first-day" breaking-in prose for a new favourite.*
*Loop pass 4: codebase-wide bug sweep — fixed `watch/list` always-empty (2 sites, same
`search_object` gotcha); full tree compiles clean. Added hidden contract clauses H25–H29
(lineage, sale/ownership, FORGET/DEVOTION, Deep Stock, and H29 — the OOC floor named
in-fiction as the one true clause).*
*Loop pass 5: incest lineage prose deepened (her own offspring breed their mother — sons &
daughters, the bloodline folded through her); mind-monitor read-out expanded to show
owner/devotion/clauses, lineage + incest-loop, trained holes/capabilities, and the FORGET
log (two improvement items resolved).*
*Loop pass 6: bug-hunt — AST-ruled-out the stray-brace `.format()` crash class across all
pool files. Content: the office "breaking frame" machine + CNC futility prose (`_CNC_BREAK`)
on the first-day breaking — in-fiction helplessness layered on top of the never-gated OOC
floor (the dread is built on the floor, not in place of it).*
