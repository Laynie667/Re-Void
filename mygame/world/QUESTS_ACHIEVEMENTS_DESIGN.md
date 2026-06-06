# Design draft — Quests, Achievements, EXP (and how they gate progression)

Status: **blueprint** (no code yet). A companion system to factions/realms: it's the
thing that makes "how far a unit gets processed" a *journey* instead of a number, and
it's the natural fuel for faction `advance: "quest"`. Bethany's note: a number going up
is dull; a unit *earning* her way deeper — unlocking the parlour, the deep stock, the
heir clause, by doing the things — is a leash she'll pull herself.

---

## A. Three linked tracks
- **EXP** — a generic per-character experience score (and optionally per-faction). Earned by
  doing things; spent/accrued toward ranks or unlocks. The blunt instrument.
- **Quests** — named, structured objectives with steps and rewards. The shaped path.
- **Achievements** — permanent, public completion badges. The trophy wall (and a gate key).

All three sit on the character and plug into the faction/realm registries.

## B. Data model (character)
```
db.exp            : {"global": int, "<faction_key>": int}     # exp pools
db.quests         : {quest_id: {"state": "active|done|failed",
                                "progress": {step_id: n}, "started", "completed"}}
db.achievements   : [achievement_id, ...]                      # earned, public
```

## C. Registries (data-driven, like FACTIONS/REALMS)
```
QUESTS = {
  "intake_orientation": {
     "name": "Orientation", "faction": "facility", "realm": "facility",
     "desc": "...", "repeatable": False, "hidden": False,
     "prereq": {"quests": [], "achievements": [], "rank": None},
     "steps": [ {"id":"sign","desc":"Sign the contract","auto":"facility_signed"},
                {"id":"milked","desc":"Be milked 3 times","count":3} ],
     "rewards": {"exp": {"facility": 50}, "scrip": 100,
                 "achievement": "first_day", "rank_unlock": None},
  },
  ...
}
ACHIEVEMENTS = {
  "first_day":  {"name":"First Day", "desc":"Completed intake.", "faction":"facility", "secret":False},
  "broodmare":  {"name":"Broodmare", "desc":"Carried a full brood to term.", ...},
}
```
Quests/achievements are **owned by a faction** (and optionally a realm), so each faction's
progression is its own — the Facility's quest line is wholly Bethany's to author.

## D. The API (world/quests.py)
- `grant_exp(char, amount, pool="global")`, `get_exp(char, pool)`.
- `start_quest(char, qid)`, `advance_quest(char, qid, step, n=1)`, `complete_quest(char, qid)`,
  `fail_quest`, `quest_state(char, qid)`, `available_quests(char, faction=None)` (prereqs met).
- `grant_achievement(char, aid)`, `has_achievement(char, aid)`, `achievements_of(char)`.
- `meets(char, requirement_dict)` — the universal gate: `{quests:[...], achievements:[...],
  exp:{pool:n}, rank:(faction,idx)}`. Used everywhere something is gated.

## E. How it gates progression (the point)
- **Faction rank:** `advance: "quest"` factions promote on quest/achievement completion;
  `advance: "exp"` on exp thresholds. (`rep` and `granted` already exist.) One unified
  `try_advance(char, faction)` checks the faction's method.
- **The Facility specifically:** gate the *depth* of processing on quests/achievements, not
  just rep — e.g. the **Deep Stock** room only opens once `perfected` achievement is earned;
  the **heir clause** unlocks after a lineage quest; new drugs/procedures unlock as quest
  rewards. Progression becomes a deliberate, authored descent instead of a meter.
- **Commands / rooms / shops:** any command, exit, or purchase can call `meets(char, req)` to
  gate access (a realm's deep areas, a faction's perks, a shop's premium stock).
- **Hooks:** the cycle's scene methods award quest progress (`advance_quest` on milk/breed/
  show/etc.); `_demote_staff`, indenture, and sales can grant/revoke achievements.

## F. Public surfaces
- `quests` / `quest <id>` — your log: active objectives + progress, available, completed.
- `achievements [<player>]` — the trophy wall; non-secret ones are public (sheet + website).
- Website: an achievements showcase + quest-line lore pages per faction (ties the portrait/
  lore-page work already on the roadmap).

## STATUS — Phase 1 BUILT
- ✅ `world/quests.py`: the engine — `db.exp/quests/achievements` model; `grant_exp/get_exp`;
  `start_quest/advance_quest`(auto-completes when steps met)`/complete_quest/fail_quest`;
  `grant/revoke/has_achievement`, `achievements_of`; `_grant_rewards` (exp/achievement/shards/
  scrip via the wallet/rank); and the universal `meets(char, req)` gate
  (quests/achievements/exp/rank). Built-in seeds + a ServerConfig-backed **custom store** so
  factions/players add their own. Tested standalone (quest flow, rewards, meets, custom authoring).
- ✅ `commands/quest_commands.py`: `quests`/`quest <id>`/`quest start|abandon` (player log);
  `achievements [player]` (trophy wall, secret-aware). **Authoring** (faction owner / builder):
  `quest create/step/reward/grant/delete`, `achievement create/grant/delete` — so faction owners
  author their own achievements and players/owners write quests beyond the built-ins, persisted.
- ⏳ Next: wire scene hooks to `advance_quest` (facility cycle milk/breed/etc.), faction
  `advance:"quest"/"exp"` → auto-promote, gate Facility depth (Deep Stock/heir/drugs) via `meets()`,
  and seed the Facility's full quest line. Sheet/website surfacing.

## G. Build phasing (when we get here)
1. `world/quests.py` API + `db.exp/quests/achievements` model + the `meets()` gate.
2. QUESTS/ACHIEVEMENTS registries (seed the Facility intake line first).
3. `quests` / `achievements` commands + sheet/website surfacing.
4. Wire faction `advance:"quest"/"exp"` → `try_advance`; gate Facility depth (Deep Stock,
   heir, drug/procedure unlocks) via `meets()`.
5. Author the Facility's full quest line (Bethany's descent) + other factions' lines.

## H. Open questions (for when we start)
- **EXP scope:** one global pool, per-faction pools, or both? (I lean: both — global for
  broad progression, per-faction for rank.)
- **Failure/regression:** can quests *fail* and can achievements be *revoked* (e.g. escaping
  the Facility strips facility achievements)? (I lean: yes, and it's very on-theme.)
- **Secret achievements:** show as "???" on the wall, or fully hidden until earned?
- **Does the Facility's grade become quest-gated** (grade = rep today), or do quests gate the
  *extras* (rooms/clauses/drugs) while grade stays rep-driven? (I lean: keep grade on rep,
  gate the depth/extras on quests — least disruptive, still transformative.)
