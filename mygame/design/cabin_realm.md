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

## 2. INVENTORY — the build scripts that already exist (reviewed 2026-06-11)

These are **copy-paste, in-game build scripts** (`@desc`, `roomzone`, mechanic `@create`,
`@open`) the user runs while standing in each room — not Python modules. They are detailed,
polished, and consistent (zones + details + study + handle + ambient + real mechanics +
inscriptions). All live in `world/*.txt`. Each opens with an `== Exits: ==` header and ends
with `@open` lines whose targets are `[#dbref placeholders]` to fill at build time.

### Helena's Log Cabin (the cabin cluster)
| Room | Script | Real mechanics / notable | Deferred ideas in-script |
|---|---|---|---|
| Front Porch & Yard | `cabin_front.txt` | porch swing / rockers / fire-pit SeatMechanics; `is_outdoor=True` (weather); **treeline zone = the forest hook** | **forest-trail exits (north/nw/west) — "wire when ready"** |
| Barn | `barn.txt` | 4 stalls (MilkingMachine + kneeling SeatMechanic each); breeding stocks (DildoSeat + RestrainMechanic yoke); **hayloft** (hay SeatMechanic cap 4 + CreakingStair ladder + dimmable lamp); tack wall w/ branding iron `R`-in-circle | **Herd State System** (HerdStateScript + `herd` cmd + roster) — explicitly deferred |
| Momo's Room | `momos_room.txt` | — | → Gargoyle's Chamber (script not found) |
| Helena's Room | `helena_room.txt` | the cabin hub: → Momo / Nursery / Passageway(out) / Kennel(in, "under the bed") / iron-ring trapdoor down → Hidden Lab | — |
| Nursery | `nursery.txt` | changing-table foam referenced by barn pads | — |
| Play Pen | `play_pen.txt` | — | — |
| Auria's Room | `auria_room.txt` | bookcase passage → Playroom | — |
| Auria's Playroom | `aurias_playroom.txt` | — | — |
| Hidden Laboratory | `hidden_lab.txt` | → Garden / Disciplination / S.I.D.M.A.U. / up→Helena | — |
| Disciplination Room | `disciplination_room.txt` | — | — |
| Garden of Knowledge | `garden_knowledge.txt` | — | — |
| S.I.D.M.A.U. | `sidmau.txt` | — | — |
| Kennel (under the bed) | `kennel.txt` | the cabin↔den seam: out→Helena's Room, **down→Shadow's Den** | — |

### Shadow's Den (beneath the cabin, via the Kennel)
| Room | Script | Real mechanics / notable | Notes |
|---|---|---|---|
| Birthing Den | `birthing_den.txt` | nest SeatMechanic (cap 4); warm-pool SeatMechanic (cap 4); pictographic lineage wall (Shadow/Whisper + WolfBred handprints + 7 named pups); column iron-rings | desc names **"rocky passages beyond"** — the natural maze-expansion seam; nest lore references **a sign at the forest's edge warning about breeding** |
| Princess' Private Space | `princess_space.txt` | bed (SeatMechanic + RestrainMechanic cuffs); cherry pillory (RestrainMechanic, height-adjustable); wardrobe MilkingMachine; little-space chest; captioned mural | south↔north with Birthing Den |

**Referenced but no script found (build or confirm in-game):** Common Area / Main Hall
(cabin_front's `in` target — possibly `common_room_commands.txt`), the Passageway
(helena_room's `out`), Gargoyle's Chamber (momos_room's `east`).

## 2b. Connectivity map (from the scripts' exit headers)

```
                          [FOREST — maze, TODO]
                                  | (treeline: n / nw / w — "wire when ready")
   Gargoyle's? — Momo's Room — Helena's Room ——(out)—— Passageway/Common Area? —(in/s)— Front Porch & Yard
        (barn: e)  |                | \                                              (is_outdoor; fire pit, woodpile)
                 Barn ——(s)————————/  |  \(trapdoor down)
              (hayloft)               |   Hidden Lab — Garden / Disciplination / S.I.D.M.A.U.
                                  (in)|
                        Nursery — Helena's Room
                       /   |   \
                Auria's  PlayPen  (s)
                  |
              Playroom
                                  Kennel (under Helena's bed) ——(down)——> SHADOW'S DEN
                                                                            Birthing Den —(s)— Princess' Space
                                                                            ("rocky passages beyond" = den maze seam)
```

## 2c. Where the maze plugs in (the user's two asks)

1. **The forest** — `cabin_front.txt` already leaves the hook: the **treeline zone** + a
   "wire forest-trail exits when ready" TODO (suggested n→Deep Forest, nw→Forest Path,
   w→Barn Trail). Skin a `MazeRoom` (or a few) as the woods off the treeline; register
   **solutions** that arrive at the real rooms (cabin front, barn, the den's outer mouth,
   secret spots), **reveals** for forest secrets, **decoys** for getting-lost. The den's
   own lore hands us the theme for free: a **sign at the forest's edge warns about
   breeding** — i.e. `maze debt` (a wrong turn can breed you) is *canon-supported* here.
2. **Expanding the den with less effort** — the Birthing Den desc explicitly names **"rocky
   passages beyond."** Skin a `MazeRoom` as those passages: one room becomes a sprawl of
   twisting tunnels, with `maze gate` body-gated inner chambers (earned-only deep dens) and
   optional `maze debt`. Big explorable den for tiny authoring — exactly the user's goal.

## 2d. THE DEN MAZE — plan + canon (user brief, 2026-06-11)

The den maze is entered through two new fixed rooms (both WRITTEN this pass, high-detail,
in the copy-paste script format — fill the `@open` dbrefs at build):
- **`world/den_forest_mouth.txt`** — *The Forest Mouth.* Winter exterior; the cave opens in
  a hillside, warm air breathing out against the cold (snow stops at a clean line). Holds the
  **canon warded breeding-sign** (the one the Birthing Den lore references), converging wolf
  tracks + upright prints that don't return, a kneeling/presenting print, offerings. Doubles
  as the forest-maze location **"the den's outside opening."** `is_outdoor=True`.
- **`world/cave_mouth.txt`** — *Mouth of the Cave.* Interior threshold; winter→blood-warm
  den-light by the step, walls polished at both walking and crawling heights, a provisioned
  **shelf station** (unlit candle / ready lead / milk bowl / stone tally), the **first pressed
  paw-print** (the lineage record's "first page"), and the **throat** that fans into the
  branching maze. Seeds the valley: a "green, sweet" smell rises from far below.

**The maze fans out from the Mouth.** `maze make` in the Den Maze room; the Mouth is its fixed
anchor. Connections to wire as `maze solution`s (and a few the user will specify):
- **The Birthing Den** (existing).
- **Other wolf-den rooms** that make sense (TBD with user).
- **A couple the user will explain** (placeholder).
- **The hidden subterranean valley** — deep, earned-only (`maze gate`), see §2e.
`maze debt` (a wrong turn breeds you) is **canon-supported** by the warded sign; intensity is
the user's call. `maze gate` fails OPEN so the floor is never trapped; confirm escape/
force_clear yanks a player out of the maze AND the valley.

## 2e. THE SUBTERRANEAN VALLEY + KAKIA (user brief — deep den set-piece, RP canon)

Deep within the den the passages open into a **hidden subterranean valley** — and it is NOT a
cave: it reads as open country, impossibly, underground.
- **A river** runs through it; **numerous trees** lead up to a single tree at the far end on
  the scale of **Yggdrasil** — a world-tree terminus.
- **A day/night cycle despite being underground** — light that rises and falls on its own
  schedule; **glowing foliage and fairy-light**; warm and green, **not winter** like the
  forest above. (Build note: a room/zone toggle script or the existing weather/time hooks
  driving a self-contained cycle; the green-sweet smell at the Mouth is its first hint.)
- **A small grove at the base of the great tree** holds a **ritual space**: a **stone
  slab/altar dedicated to Kakia**.
- **Kakia** — established here as a **goddess associated with wolves and with futanari-at-
  will** (becoming/granting a futa form by her favor). Proposed real hooks (for the user to
  confirm/shape):
  - A **statue that changes** (state-driven description — phase/devotion/offering count).
  - **Offerings** → **blessings**: route through REAL systems, not flavor — e.g. a body/
    transform grant (futanari-at-will via the existing body/transform system), a fertility/
    breeding boon, a wolf-bred standing bump. An `offer`-style verb at the altar + an
    offerings tally on the statue.
  - §0: any blessing that alters the body must be reversible by the floor; any new flag
    (Kakia's favor / granted-futa / pack standing) registered in the realm reset spec.
- OPEN for the user: Kakia's exact blessings + their costs; whether the valley is purely a
  reward space or also has its own dangers/scenes; who/what tends the grove.

## 2f. THE FOREST MAZE — winter location list (user brief)

Winter-themed forest rooms to exist as **forest-maze locations** (skinned `MazeRoom`(s) off
the cabin-front **treeline**; solutions → places, reveals → secrets):
- **The trail up to the cabin** (→ links to the cabin area; the cabin-side end will be added
  directly to the cabin as the user plots the cabin out more).
- **The den's outside opening** — = `den_forest_mouth.txt` (written; see §2d).
- **Ruins** of some kind that feel **magical and perverse**.
- **A stream.**
- **A path up a cliff's edge** *(later planning — placeholder).*
- **A clearing with a small encampment near the waystone** = the **realm entrance** (where
  the realm relinks in; see §3 Q1).
- *(The path to the barn will be added directly to the cabin's area, not the forest maze.)*
- NPCs of the area: deferred ("when we can").

---

## 3. Open questions (the user answers one by one — no building ahead of these)

Geography and most room content are now KNOWN (see §2). What's genuinely open:

1. **Relink point:** where does this realm attach — a hub waystone word, an existing exit,
   a standalone realm reached how? (The cabin cluster is internally complete; it just needs
   a way *in*.)
2. **Forest shape:** how many maze rooms, which **solutions** map to which real rooms
   (cabin front / barn trail / the den's mouth / secrets), and which secrets are **reveals**
   (prose) vs. walk-to-a-place. Mode `classic` (punishing) or `forgiving`?
3. **`maze debt` (breeding-on-lost):** on for the forest and/or den? (Canon-supported by the
   "sign warns about breeding" lore — but the user's call on intensity.)
4. **Den expansion:** how deep do the "rocky passages" go, and which inner chambers are
   `maze gate` body-gated (earned-only) — and gated on *what* (conditioning / a wolf-bred
   standing / a pack-membership flag)?
5. **Barn Herd State System:** build the deferred `herd` roster/command now, or leave it
   until the barn has active occupants (as the script itself suggests)?
6. **The §0 floor:** confirm any NEW persistent flag this realm introduces (pack membership?
   wolf-bred status? maze debt counters?) gets registered in a realm reset spec so
   `escape`/`force_clear` always clears it. The cabin↔den seam (Kennel "down") and the maze
   must never be a stuck-spot.

## 3b. Build order, once a section goes READY (suggested)

1. Run the existing room scripts in dependency order, filling the `@open` dbrefs as rooms
   are created (the cabin cluster first — Helena's Room is the hub — then the den via the
   Kennel). *These are the user's to paste in-game, or I can convert any to a Python
   `build_cabin()` entrypoint with real dbref-resolution + tagging if wanted.*
2. Confirm/locate the referenced-but-unscripted rooms (Common Area, Passageway, Gargoyle's).
3. Place the forest maze off the treeline; wire its solutions to the now-real dbrefs.
4. Place the den's "rocky passages" maze; set any body-gates.
5. (Optional) the Barn Herd State System.
6. Relink the whole realm at its chosen entry; verify the OOC floor across the new flags.

---

## 4. Build discipline (when a section goes READY)

Same as the facility: reuse the real systems; `python3 -m py_compile` + a standalone logic
test for anything dependency-light; one build entrypoint + one teardown; tag everything
(`category="realm"`/`"area"`) for precise teardown; register any new persistent db flag in
the realm's reset spec so `force_clear`/`escape` clears it; keep both build & reset paths in
sync; commit + push per increment. Update this doc as each piece lands.
