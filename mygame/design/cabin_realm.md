# The Cabin Realm — design & plotting (living doc)

*Status: PLOTTING. The cabin, barn, and shadow's den already exist in-game (live DB
objects). This doc is the shared workspace; the user writes up ideas one by one, and
each gets folded in here before any building. Nothing is built from this doc until a
section is marked **READY**.*

---

## 0. The premise (as the user has framed it)

A realm centred on **the cabin** — already built in game. The plan:
- **Relink** the cabin to wherever in the realm the user decides (it's portable; just
  re-point its exits / waystone address).
- **Expand the barn** and the **shadow's den** (both already exist — grow them, don't
  rebuild).
- Use the **maze room system** for the **forest**: exploring it, finding its secrets and
  hidden locations — and *also* to make the **den more expansive with less effort** (a
  maze is a lot of explorable space for little authoring).

The user owns direction here exactly as with the facility. The §0 OOC floor (see
`CLAUDE.md`) is sacred in this realm too: whatever locks/dread the forest or den hold
in-fiction, `escape`/`force_clear`/the superuser purge always work and are never gated.

---

## 1. Systems we already have to build this on (no new engines needed)

- **Maze** — `world/maze.py` (pure logic, unit-tested) + `typeclasses/maze_room.py`
  (`MazeRoom` + `MazeCmdSet`) + the `maze` builder command (`commands/builder_commands.py`).
  Directional moves loop back on themselves; a per-character sequence (`ndb.maze_seq`)
  tracks the combo; completing a registered **solution** teleports to its destination (or
  fires a prose-only reveal); anything else fires a **decoy**. Modes: `classic`
  (reset-on-wrong) and `forgiving` (trailing-match). Build verbs:
  - `maze make`
  - `maze solution <name> = n n e w > #<dest>` (a combo that opens a path/location)
  - `maze reveal <name> = <prose>` (a secret that's shown, not walked to)
  - `maze gate <name> = conditioning 80` (body-gated: refuses to open until a stat ≥ N;
    **fails OPEN on error so the floor is never trapped**)
  - `maze debt 0.3` (opt-in: a wrong turn has a chance to breed you — real
    `gang_inseminate` — before looping you back; getting lost *is* the content)
  - `maze decoy add`, `maze mode classic|forgiving`, `maze show`
  → This is the engine for **the forest** (find your way to real locations + secrets) AND
    for **a bigger den** (one MazeRoom skins as many "twisting passages" as you like for
    almost no authoring).
- **Realm build pattern** — `world/realm_build.py` (`build_realm`/`teardown_realm`/
  `force_clear`) + tagging discipline (everything tagged for precise teardown). The cabin
  realm gets the same treatment: one build entrypoint, one teardown, every created object
  tagged (proposed: `tags.add("cabin_realm", category="realm")`).
- **Waystone travel** — a `HubWaystone` hears a spoken word and teleports the speaker to a
  matching `Waypost`/`PortalWaystone`. This is how the cabin **relinks** into the realm
  (and how a hidden return stays hidden until earned: leave the return address unset).
- **Zones / rooms / fixtures** — the room-zone system (`{zone:<name>}` tokens, un-gettable
  fixtures) is exactly what we used for the post office; the barn and den expansions reuse
  it verbatim.
- **Furniture / scenes / CYOA** — self-releasing FurnitureSessionScripts (rocking horse,
  spiral chair, the Break Room couch) and the CYOA spine (`world/cyoa.py`) are all
  realm-agnostic; the barn and den can carry their own scenes/choices the same way.

---

## 2. The pieces, as we understand them so far

### 2a. The cabin  *(exists — relink)*
- TODO (user): where in the realm should it sit? What's the approach to it — a forest path
  (maze), a waystone word, a plain exit?
- Build cost: low. Mostly re-pointing exits / setting a waystone address.

### 2b. The barn  *(exists — expand)*
- TODO (user): what's the barn *for* in this realm? (livestock/breeding annex to the
  facility's themes? storage-of-people? a stage?) What rooms/stalls/lofts does it grow?
- Likely reuses: stalls as zones, breeding/milking mechanics already built, restraint
  furniture.

### 2c. The shadow's den  *(exists — expand, maze-assisted)*
- TODO (user): the den's nature/tone, and what lives in it. The maze can make it sprawl
  (twisting dark passages, rooms that loop) for little authoring — `forgiving` or `classic`
  mode TBD per how punishing we want getting-lost to be.
- Open: does the den use **breeding-debt halls** (`maze debt`) or stay non-breeding and
  atmospheric? Body-gated depths (`maze gate`) for earned-only inner rooms?

### 2d. The forest  *(new — maze)*
- The connective tissue: a MazeRoom (or a few) skinned as woods. Registered **solutions**
  lead to real locations (the cabin, the barn, the den, secret spots); **reveals** are
  forest secrets shown in prose; **decoys** are the getting-lost beats.
- Open: tone (fairytale-menace? predatory? liminal?), and which locations are solutions vs.
  hidden reveals.

---

## 3. Open questions (the user will answer one by one — no building ahead of these)

1. **Geography:** rough map — what connects to what? (forest ↔ cabin ↔ barn ↔ den, and how
   you get between them: maze paths, waystone words, plain exits?)
2. **Tone of the realm** vs. the facility — is this softer/wilder/predatory/fairytale, its
   own register, or an annex of the facility's themes?
3. **The barn's purpose** and what it grows into.
4. **The den's nature** and how hard "lost" should bite (atmospheric vs. breeding-debt vs.
   body-gated depths).
5. **The forest's secrets** — what's worth finding out there, and what's solution
   (walk-to-a-place) vs. reveal (prose secret)?
6. **Entry/exit & the floor:** how you *get into* the realm (and the always-open OOC exit —
   confirm the §0 floor covers any new persistent flags this realm introduces).

---

## 4. Build discipline (when a section goes READY)

Same as the facility: reuse the real systems; `python3 -m py_compile` + a standalone logic
test for anything dependency-light; one build entrypoint + one teardown; tag everything
(`category="realm"`/`"area"`) for precise teardown; register any new persistent db flag in
the realm's reset spec so `force_clear`/`escape` clears it; keep both build & reset paths in
sync; commit + push per increment. Update this doc as each piece lands.
