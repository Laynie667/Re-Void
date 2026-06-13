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
| Sorting Hall + Dead Letter Cage | ✅ Built (post_office_build) |
| Quiet Room + drawer/wax-kit/PENDING tray | ✅ Built (post_office_build) |
| Seraphine's Parlour (+ toybox, hatbox of unsent letters) | ✅ Built (post_office_build) |
| Calix's Keeping-Room (+ toybox, confiscated note) | ✅ Built (post_office_build) |
| Vesper's Nest (+ toybox, the half-erased Declaration) | ✅ Built (post_office_build) |
| `clerk` counter menu (CYOA: tutorial + gossip) | ✅ Built (cyoa `clerk`/`clerk_gossip`, `CmdClerk`) |
| `services` menu (CYOA: real officiating + delivery/body-work/poste routing) | ✅ Built (cyoa `post_services`/`post_officiant`, `office_officiate` effect) |
| Gossip pool (sibling secrets, the "tried-on holes" beat, 3 a.m. drawer) | ✅ 10 entries (`post_office_build._GOSSIP`) |
| The Break Room (shared space: rota / keepsake shelf / under-couch basket) | ✅ Built (up the back stairs off the Sorting Hall) |
| Poste restante — real persistent letter drop (`poste leave`/`poste read`) | ✅ Built (`CmdPoste`, `leave_poste`/`draw_poste` on the office room) |
| Poste wired into the services menu (real drop/read from inside CYOA) | ✅ Built (cyoa `post_poste` + `office_poste` effect) |
| Per-sibling gossip voices (Calix spare, Vesper oblique) | ✅ Built (`_CALIX_GOSSIP`/`_VESPER_GOSSIP`, `clerk_gossip` reads present clerk) |
| Break Room off-duty couch scene (consensual, warm, real arousal) | ✅ Built (cyoa `break_couch`/`break_couch_after`, `CmdUnwind`) |
| Poste "ripening" beat — old letters deliver themselves (live cage) | ✅ Built (`ripen_poste` + `PosteRipenScript` on the Sorting Hall) |

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

## QUALITY REWORK — bringing the office to cabin-grade (in progress)

The first office build used flat `@desc` + un-gettable fixture Objects + a paragraph
`physical_desc` on each clerk. Next to the cabin/den rooms (full `roomzone` zone builds —
layered `detail`/`study`/`handle`/`inscribe` + real mechanics + deep ambient), that reads
~1/10. The fix: re-author the office on the same **zone system**, to the same density.

- **Rooms → `roomzone` paste scripts** (run standing in the existing room; overwrites the flat
  desc with a zone build, leaves exits alone). FLAGSHIP DONE: `world/post_office_sorting_hall.txt`
  (zones: tubes / pigeonholes / ladder / counter / cage; detail+study+handle+inscribe; real
  SeatMechanic stool + ladder-step + CreakingStair; 8-line ambient). This is the bar.
- **TODO rooms (same treatment):** Front Office, Quiet Room, Seraphine's Parlour, Calix's
  Keeping-Room, Vesper's Nest, The Break Room.
- **Clerks → character `zone`s.** Each clerk gets body/prop zones (hands, tail/horns, lanyard,
  smile, the letter they're holding, etc.) with detail/study/handle, and a `physical_desc` that
  embeds `{zone:...}` tokens — same depth a room gets. NOTE: the `zone` command edits the
  CALLER's body, so clerk zones are installed by puppeting the NPC or by an `@py` zone-dict
  injection matching `roomzone_commands._blank_zone`. TODO for Seraphine / Calix / Vesper.

## KNOWN ISSUE — misrouted return exits (investigating)

After the wrong-office mis-build + repair, some exits don't return to the room they should.
Diagnose with the exit-graph `@py` (dumps each post_office room's exits + destinations); fix
in the builder/repair once the graph identifies the offenders. Do NOT re-dig to "fix" an
exit (that risks duplicate rooms) — repoint the existing exit instead.

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

## Lore (canon): the Vesper favour

Three winters ago a facility contract crossed Vesper's counter alone and came back with one
of their ambiguous riders — readable two ways, and the second way was a DOOR: an out from one
of Bethany's bindings, mercy dressed as imprecision, from the clerk who sides with nothing.
Bethany caught it on audit. Rather than raise it (Vesper's first irregularity on record would
have meant Vesper being *examined* — made to declare an intention, to be READ — and Bethany
doesn't break load-bearing things), she quietly had the resident re-sign a fair copy and filed
the original, soft spot intact, in her own drawer. Unread, officially. Unraised, permanently.

Both know. Neither has ever said a word. Bethany's parcels go to the top of the sort; Vesper
can't meet her eyes, which from Vesper is a confession and a thank-you in one gesture.

**The standing favour:** Bethany keeps Vesper's one act of taking-a-side sealed, the way Vesper
keeps everyone else's letters. Spent so far: one unsupervised afternoon in the Sorting Hall
(the post_office_build survey). **Earmarked remainder:** when the maze is placed, Vesper's
counter carries the maze MAPS (see Maps backlog item) — no questions, no riders.
Build hooks: the filed original could be a readable in Bethany's office; the map-vending wires
Vesper into the maze economy; the rider's "door" is a ready-made plot if a resident ever finds
the fair-copy discrepancy.

---

## The siblings' pocket rooms (built — `post_office_build._build_pockets`)

Three private spaces, one per clerk, dug off the public ones. Each holds a toybox
(un-gettable readable fixture) and one "secret" fixture — the embarrassing/tender lore.
Idempotent; tagged `post_office`/`area` for teardown. **§0:** the way in and the way out
are always open exits — nothing here locks, gates, conditions, or traps.

- **Seraphine's Parlour** — through `the standing mirror` in the Quiet Room (a one-way
  window back onto where people decide things). Fixtures: `seraphine's toybox` (silk
  rope, "the negotiator", name-labelled wax, a stamped harness, a punishment lottery of
  delivery slips, and Vesper's first knitted tail at the bottom); `the hatbox of unsent
  letters` (the three of them writing each other true things and never sending them).
- **Calix's Keeping-Room** — through `the strong door` off the Sorting Hall. The tidiest
  erotic space in the world; restraints graded by width, gags by decibel, a sorting-grid
  of one-card memories (`STAYED.` with an empty slot). Fixtures: `calix's toybox` (silent
  hinges, an un-labelled worn-smooth wax die, a counting-frame "for counting. she knows
  what.", a twice-signed receipt); `the confiscated note` (Seraphine's noticeboard tease
  about the re-oiled bench + his one-word answer, both filed).
- **Vesper's Nest** — through `the fold in the corner` of the Sorting Hall (only a corner
  if they've let you in). The one undraped mirror in the building. Fixtures: `vesper's
  toybox` (the wardrobe of *parts* — the thing Seraphine gossips about — that they try on
  alone and always put back, with the two cards in the lid); `the declaration form` (the
  real DECLARATION OF NATURE, filled and erased to cloth; "the open is the answer").

## The Break Room (shared space — the heart of the place)

Up the back stairs off the Sorting Hall (`back stairs` / `up`). The room the public counter
is a performance *for*: the three off-duty, faces unheld. Fixtures (un-gettable readables):
`the chore rota` (Calix's grid hijacked by two other pens — Vesper's quiet washing-up
confession, Seraphine outranking the rota for Calix's birthday, the biscuit thief left to
live with it), `the keepsake shelf` (three candid photos incl. the only surviving one of
Vesper, "proof of life"), and `the basket under the couch` (communal, unbothered — house
rules: ask first, tease always, Vesper owes four stories). Tagged post_office/area.

## Poste restante — the Dead Letter Cage (a real, persistent drop)

`CmdPoste` (`poste` / `sift`, in ALL_FACILITY_VERBS, self-gating to the office complex):
  * `poste` — status (how many letters held) + how-to
  * `poste leave <words>` — seal a letter into the cage (anonymous, persistent)
  * `poste read` — draw one held letter and read it, *preferring someone else's over your own*
Letters persist on the office room's `db.poste_letters` (one shared store across the complex),
capped at `_POSTE_MAX` (60; oldest ripen out on overflow). Helpers `leave_poste`/`draw_poste`/
`poste_count` in `post_office_build`. Real cross-player content: what you leave stays and
others can find it. No gating — purely additive; the cage's third lock is decorative.

**Ripening beat (live cage).** `PosteRipenScript` (in `typeclasses/scripts.py`) attaches to
the Sorting Hall at build time (idempotent) and, on a slow jittered timer (10–20 min) when
someone's present, calls the pure `ripen_poste(office)`: the OLDEST letter past `_RIPEN_AGE_S`
(3 days) quietly "delivers itself" (popped) and a single atmospheric line broadcasts. Reveals
NO content — the office never reads them (canon). Keeps the cage feeling alive and bounded.
Unit-tested (`test_poste_ripen`): age-gated, oldest-first, content never leaked.

## Per-sibling gossip voices + the couch scene (CYOA)

- **Gossip in the present clerk's register.** `clerk_gossip` now reads `_present_clerk()` (who's
  actually in the room) and pulls from that clerk's pool with matching 'another'/'back' beats:
  Seraphine (`_GOSSIP`, 10, warm), Calix (`_CALIX_GOSSIP`, 5, spare/devastating — sets one true
  thing on the counter), Vesper (`_VESPER_GOSSIP`, 5, oblique/blushing — tells you more by what
  they won't finish). Random among present; default Seraphine.
- **Poste from inside the menu.** The services "poste" option now chains to `post_poste`, which
  REALLY drops one of a few pinned unsendables into the cage (the `office_poste` effect calls
  `leave_poste`), draws one to read (`mode:read`), or points at `poste leave` for free text.
- **The Break Room couch scene** — `CmdUnwind` (`unwind`/`couch`, gated to the Break Room with a
  clerk present) poses `break_couch`: an off-duty, **consent-forward** scene with whoever's up
  there, each sibling in their own register (Seraphine possessive-warm, Calix quiet-solid, Vesper
  shy-fervent). House rule in-fiction AND as the §0 floor: they ask first; "Not today" is a clean,
  unwounded out. Yes moves real arousal (`couch_warm` → arousal_script); rest gives comfort; both
  chain to `break_couch_after` (the afterglow). Warm-domestic register, no gate, no conditioning —
  the one room that was never a transaction.

## The services menu — `clerk` → "Ask what they can do for you" (CYOA, real)

`post_services` is the office's actual service directory (reached from the `clerk` menu, or
deep-linked). Unlike a tutorial, **officiating actually fires here**: pick "Officiate a
contract I'm carrying" → `post_officiant` finds the nearest unsigned `MilkingContract`
(inventory then room, mirroring `MilkingContract._find_contract`) and offers the three clerks,
each routing the REAL `world.post_office.officiate()` via the `office_officiate` effect — Calix
flat (a fee, nothing added), Vesper a free ambiguous rider, Seraphine free + a hidden clause
("you'll see what it cost you eventually"). No contract to hand → Seraphine says so and points
at `contract draft`, bouncing back. The other services route honestly to their real station:
DELIVERY → the `ogram` system, BODY-WORK → Durgin, POSTE RESTANTE → the Dead Letter Cage. No
faked outcomes; the one that claims to do something does it.

## The counter menu — `clerk` / `counter` (CYOA, no say-triggers)

`CmdClerk` (in `ALL_FACILITY_VERBS`, available game-wide; self-gates to rooms tagged
`post_office` or where a clerk is present) poses the `clerk` CYOA node. Drive with
`choose <n>`. Half service-desk **tutorial** (drafting → clauses → officiate/cosign, who
reads flat / who riddles / who kisses-it-through), half **gossip**: the `clerk_gossip`
node picks one of six fond, filthy little stories fresh each time and loops ("tell me
another") or returns to the menu. Pure prose — no effect, no gate (§0-safe by
construction). The gossip pool (`post_office_build._GOSSIP`) is the requested "I once
caught Vesper trying on different parts/holes" beat plus Calix's re-oiled bench, the
unsent letters, how officiating works, why the doors don't lock (an in-fiction statement
of the floor), and the bakery watcher in the Dead Letter Cage.

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
