# The Postal Office — Design Reference
*Room built. NPCs pending. Do not spawn until scripts are written.*

---

## Status

| Element | Status |
|---|---|
| Room dug (#32) | ✅ Done |
| rdesc / rentry / rexamine | ✅ Done |
| rtime layers | ✅ Done |
| rweather layers | ✅ Done |
| Ambient pool + AmbientScript | ✅ Done |
| Seraphine NPC | ✅ Spawned (post_office_build) |
| Calix NPC | ✅ Spawned (post_office_build) |
| Vesper NPC | ✅ Spawned (post_office_build) |

---

## Location

Dug west from the Wayfarer's Hall (#2). Exit aliases: `west`, `postal office`, `post`, `post office`, `ogram office`.

---

## The NPCs

These three are already fully characterized in `commands/ogram_commands.py` — their appearance, personality, and delivery behavior are all established there. The in-room NPC versions should match that source exactly.

### Seraphine
**Station:** Left end of the counter — warmest, slightly cluttered workstation.
**Appearance:** Crimson-skinned tiefling woman. Small swept-back horns. Expressive tail. The particular poise of someone who has heard every kind of secret and found most of them charming rather than shocking.
**Personality:** Warm, knowing, unhurried. Entirely at home in other people's private moments. Will look up when someone enters and take them in with obvious interest.
**Look desc:**
```
Seraphine occupies the left end of the counter the way she seems to occupy most
spaces — entirely, and without apology. Crimson-skinned, small swept-back horns,
a tail that moves with an expressiveness she doesn't bother to suppress. She is
reading the front of a sealed letter with the expression of someone who could
absolutely open it if she wanted to and has chosen, generously, not to. She looks
up when the room changes. She takes you in with the particular warmth of a woman
who has heard every kind of secret and found most of them charming rather than
shocking.
```

---

### Calix
**Station:** Center of the counter — immaculate workstation, everything at a right angle.
**Appearance:** Deep charcoal-skinned tiefling man. Ram horns. Broad-shouldered. Built like someone designed for considerably more demanding work than this.
**Personality:** Few words. Absolute discretion. Unhurried solidity. Glances that hold one beat longer than necessary, then return to work as though you imagined the extra beat.
**Look desc:**
```
Calix stands at the center of the counter with the unhurried solidity of something
built to last. Deep charcoal skin, ram horns, the broad-shouldered patience of a
man who has carried stranger parcels than this in worse weather and arrived looking
entirely unbothered. He is sealing a letter with three precise impressions of the
stamp — no more, no fewer. He glances up without expression. The glance holds a
beat longer than necessary. He returns to his work as though you'd imagined the
extra beat, which is probably what he intended.
```

---

### Vesper
**Station:** Far right of the counter — minimal workstation, only the bare essentials.
**Appearance:** Opalescent-skinned tiefling of undisclosed nature. Swept-back horns that shift between sharp and softer depending on the light. Eyes that change color: silver, then violet, then something without a name.
**Personality:** Speaks rarely. Deliberately unreadable. Can be flustered by direct attention — will find something nearby to focus on intently. Their nature has never been stated and they prefer it that way.
**Look desc:**
```
Vesper is at the far right of the counter, their attention apparently absorbed by a
sorting task that doesn't seem to need quite this much focus. Opalescent skin.
Swept-back horns that catch the lamplight differently every time you look. Their
eyes, when they briefly track across the room, are silver — then a color that sits
somewhere between violet and something that doesn't translate. They are holding a
letter marked |xAffection — Grope — Anonymous|n with the focused neutrality of
someone who processes these regularly and has developed a professional relationship
with the fact.
```

---

## Notes for Implementation

- All three share the same physical space. Only one or two may be "present" at a time depending on future scheduling logic, or all three can be present simultaneously.
- They do not need dialogue trees at first — a `look seraphine` / `look calix` / `look vesper` with the above descs is sufficient to establish them.
- Longer term: could tie them to the ogram delivery system so they "leave" when carrying a message and "return" after delivery.
- Their ambient contributions are already seeded in the room's ambient pool and reference all three by name.

---

## Spawn Command

✅ BUILT — `@py from world.post_office_build import build_post_office; build_post_office(me)`
Idempotent: spawns the three clerks (canonical descs), digs + connects the Sorting Hall (Dead
Letter Cage easter egg) and the Quiet Room (amendments drawer / wax kit / PENDING tray easter
eggs), merges deepened ambient into all three rooms. Tagged post_office/area for teardown.
Reference file: `commands/ogram_commands.py` for full character details.

---

## BACKLOG — NPC & content layer (the engine is built; these are content on it)

The contract authoring + officiating engine is live (`contract draft/clauses/
officiate/cosign`, `world/post_office.py`, the `own` effect + multi-owner, the
§0 revert). What's pending is the *people* and the set-pieces:

### NPCs to spawn
- [ ] **Seraphine / Calix / Vesper** — in-room NPC versions (descs above; spawn
      pattern = `durgin_spawn.py`). They are the officiant vectors already wired
      into `post_office.officiate()`.
- [ ] **Durgin** — brander / piercer / smith. Functional body-mods routed through
      the REAL systems (`add_piercing`/`PiercingItem`, `record_mark` freeform
      marks, brand application). `durgin_spawn.py` already exists — flesh out.
- [ ] **Bethany** — already provisioned via `bethany_script.provision_bethany`;
      needs the Seraphine relationship hook (see below).
- [ ] **Wren / Sable** — Seraphine's other partners (vessel-deposit targets).
- [ ] **Auria** + the **futa-eevee plush** in her room/playroom
      (`auria_room.txt`, `aurias_playroom.txt` already drafted).

### Seraphine's contract — FORCED ADOPTION + unbirthing (her signature)
The thesis of her character: not ownership on paper but *"I'm taking you home."*
- [ ] `seraphine_offer` contract bundle — visible clauses read like a foster
      placement; hidden clauses are the womb. Sits on the `own` effect + a new
      relation role `ward`/`dependent` (add to `relationships._apply` roles).
- [ ] **Worldbuilding glue:** Seraphine visits facility **auctions**, works deals
      with **Bethany** for choice **Deep Stock** product — gives her a logistics
      reason to exist (she's a *buyer*) and ties post-office ↔ facility.

### EXPAND existing `WombRoom` — captive carry (unbirthing) [NOT a new subsystem]
`typeclasses/womb_room.py` + `womb_commands.py` ALREADY provide the vessel: an interior
room on an orifice/`both` zone, `enter <host> [zone]`, fluid + flood states, shaft-visible
messages, host `pulse` inward. Seraphine's "carry a captive" is an EXPANSION, four deltas:
- [ ] **Held/captive mode** — resident can't self-`leave`; exit gated on host-release or a
      signed contract (same lock as the eevee plush). The one genuinely new piece.
- [ ] **Host-visible status** — a line on the HOST's `look` ("her belly shifts — someone's
      *in* there"); WombRoom currently renders interior/flood only from inside.
- [ ] **§0 CHECK (blocking):** WombRoom sets `jump_protected=True` — VERIFY `escape`/
      `force_clear` overrides it and yanks a held captive out before shipping captive mode.
- [ ] **Deposit / transfer** a captive between hosts (Seraphine -> Bethany / Wren /
      Sable). Helper over install/uninstall. Witness the holder fucked from inside.

### NEW room type — combination-lock / "Lost Woods" maze room  [BUILT — core]
`world/maze.py` (pure logic, unit-tested) + `typeclasses/maze_room.py` (MazeRoom +
MazeCmdSet) + `maze` builder command (`commands/builder_commands.py`). Directional
moves loop back; per-char `ndb.maze_seq` tracks the combo; completing a solution
teleports to its destination (or prose-only reveal), everything else fires a decoy.
classic (reset-on-wrong) + forgiving (trailing-match) modes both tested.
Build in-game: `maze make`, `maze solution deeper = n n e w > #84`, `maze reveal`,
`maze gate <name> = conditioning 80`, `maze debt 0.3`, `maze decoy add`,
`maze mode classic|forgiving`, `maze show`.
- [x] Per-char sequence, solutions, decoys, two modes, builder command.
- [x] **Body-gated exits** — a solution can refuse to open until conditioning/regression/
      devotion/standing ≥ N, or breeding quota met (`quota_met`). Fails OPEN on error so the
      floor is never trapped. The halls make you earn your way out.
- [x] **Breeding-debt halls** — opt-in per-move chance a wrong turn breeds you (real
      `gang_inseminate`) before looping you back; getting lost IS the breeding.
- [ ] Skin + place actual instances: facility "hallway after intake"; forest in the
      hub / cabin realm. (Needs the realm flesh-out below.)

### NEW item type — Maps (maze hint item + general navigation)  [TODO]
A readable `Map` item. Two jobs, one typeclass:
1. **Maze hint** — bound to a MazeRoom + solution name; `read map` returns
   `MazeRoom.solution_hint(name)` (the combo, possibly redacted/partial per tier).
   Vesper sells these; ties the NPC economy to traversal.
2. **General map** — a readable that reveals a region's room links / a "cool spot"
   (random keyed room). Charges/uses optional. Reuses readable-item plumbing.
- [ ] `typeclasses/map_item.py` (Map) + `read`/`study` hook.
- [ ] Partial-hint mode: high facility standing = fewer redacted steps (cruel: she
      *makes* you earn your way out of her halls).
- [ ] Wire Vesper's stock + a price; place one maze instance to test against.

### Realm flesh-out (broader backlog)
- [ ] Update / improve the Facility (ongoing per FACILITY_SYSTEMS_CATALOGUE backlog).
- [ ] Flesh out the **hub realm**.
- [ ] Flesh out the realm the **cabin** belongs in.

### Scenario-trap — the futa-eevee plush (trigger-fires-contract)
- [ ] Player crawls into the plush's orifice (a container room); the only exit is
      lock-gated on `contract.signed`. Seraphine whispers clauses the eevee
      "executes" — editing the contract the player must sign to be let out.
- [ ] Same §0 rule: `escape`/`force_clear` springs the plush and voids the unsigned
      contract regardless of state.
