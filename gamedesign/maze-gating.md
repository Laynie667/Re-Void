# Maze & Gating — guide and how-to

*Status: **[BUILT]** — `typeclasses/maze_room.py`, `world/maze.py`, `commands/builder_commands.py
::CmdMaze`. This is the live behaviour; the "gate" half is the prototype for the universal
Reveal/Gate primitive (see `gate-conditions.md`).*

---

## What a maze is
A `MazeRoom` is a "Lost Woods" room with **no normal exits** — directional moves (`n`, `e`, …)
*are* the puzzle. Each move appends to a per-character sequence (`ndb.maze_seq`). Walk a
registered **solution** combo and you're teleported to its destination (or shown a prose-only
**reveal**); walk anything else and you get a **decoy** line. Modes: `classic` (a wrong move
resets the combo) or `forgiving` (trailing-match — the tail of your moves is checked).

One MazeRoom can be skinned as many "twisting passages" — lots of explorable space for almost no
authoring. Great for forests and sprawling dens.

---

## Builder commands (`maze`, Builder lock) — exact syntax
Stand in the room you want to configure (it must have no normal exits).

```
maze make [<name>]                      — make/dig this room a MazeRoom
maze solution <name> = <dirs> > <dest>  — add/replace a solution; dirs space/comma-separated;
                                          dest = room dbref/#id (optional — omit for reveal-only)
maze reveal <name> = <prose>            — set the prose shown when that solution is walked
maze gate <name> = <type> [<min>]       — gate a solution on body state (see below; "none" clears)
maze decoy add = <line>                 — add a wrong-turn line (use {dir} token)
maze decoy clear                        — reset decoys to defaults
maze debt <0..1> [<species>]            — breeding-debt halls: chance a wrong turn breeds you
maze mode classic|forgiving             — wrong move resets the combo, or not
maze show                               — show this room's full maze config
```

### Worked example
```
maze make The Lost Hallway
maze solution deeper = n n e w > #84
maze reveal  deeper = The corridor finally stops doubling back on itself.
maze solution back   = s s > #2
maze gate    deeper = conditioning 60
maze mode classic
```
A traveller must (a) walk `n n e w` **and** (b) have `conditioning >= 60` for `deeper` to open.
Below 60 they get a gate-denial line even with the correct turns; `back` (ungated) always works.

---

## Gating — the heart of it
A **gate** on a solution makes a correctly-walked path refuse to open until a **body condition**
is met. Logic: `MazeRoom._gate_ok(caller, name)`.

- `maze gate deeper = conditioning 80` → opens when `db.conditioning >= 80`.
- `maze gate inner = devotion 60` → `db.bethany_devotion >= 60`.
- `maze gate pit = quota` → opens when the breeding quota is met (no number).
- `maze gate deeper = none` → removes the gate.

Condition **types** (current): `conditioning`, `regression`, `devotion`, `standing`, `quota`.
Full catalogue + proposed extensions in `gate-conditions.md`.

When the gate isn't satisfied, the move is recognized as *correct-but-not-yet*: the traveller
gets a denial line (`maze_gate_denials` pool, or a per-solution `gate_denial`), e.g. *"the way
folds shut as you approach — not yet."* They keep the combo; they just can't pass until their
state climbs. **It's earned by who you've become, not by a harder puzzle.**

### The load-bearing rule: gates FAIL OPEN
`_gate_ok` returns `True` on any error or unknown type (line ~215). A broken or mistyped gate
**opens** rather than trapping anyone. This is the §0 floor expressed in the mechanic: a gate is
a *bonus lock*, never a way to wall someone in. **Carry this rule into every reuse of the
primitive** — a gated detail, exit, or seat must always fail open.

---

## `maze debt` — getting-lost as content
`maze debt 0.3 [species]` gives each wrong turn a 30% chance to breed the traveller (real
`gang_inseminate`) before looping them back. Canon-supported where the lore warns of it (e.g.
the den's "sign at the forest's edge"). Intensity is the builder's call; 0 = off.

---

## Reuse: the same gate on non-maze things  [ROADMAP]
The gate check is small and general. The plan is to let the **same condition dict** gate a
room/body **detail**, **handle**, **study**, **mechanic**, or **ordinary exit** — hidden from
`look`/`survey` until satisfied, always failing open. See `rooms-and-roomzones.md` (Reveal/Gate
primitive) and `gate-conditions.md`. Examples: wall-words that only the conditioned can read; a
hidden exit revealed by `study`; a jacuzzi whose dildos are undescribed until you `sit`.

---

## Build discipline
- Apply to a room with **no normal exits**.
- Gate on stats that actually move in play (conditioning/devotion/standing accrue; quota is a
  clean binary).
- Confirm `escape`/`forceclear` yanks a traveller out of the maze (and any gated-deep area) —
  the maze must never be a stuck-spot.
- `maze show` to audit a room's config.
