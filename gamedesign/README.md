# gamedesign/

**Blueprints for systems that have proven out.** When a feature/system works for you and
your players in the live trial-and-error game, write it up here as a clean, complete spec so a
fresh, curated copy of the game can be built later from only the things worth keeping.

One file per system (e.g. `conditioning.md`, `cyoa-scene-engine.md`, `gang-breeding.md`,
`facility-hub.md`). Use `TEMPLATE.md` as the starting shape.

> Contents here are **gitignored** (except this README + TEMPLATE) — keep your working
> blueprints on your local machine. Promote a finished one into the tracked repo when you're
> ready to build the fresh copy.

## Doc set — Rooms (the first proven system, fully documented)
Start with the layer above, then the rooms:
0. **`world-layer.md`** — the world *above* rooms: Realms (owned by Factions), the Clock, Weather/
   Climate, World-State modes, Events/scheduler, the Economy (shards + Wallet + arrears + the
   seizure ladder), and Travel (waystones). Rooms inherit from their Realm.
1. **`rooms-and-roomzones.md`** — the blueprint: the system as-is + the universal Reveal/Gate
   primitive + the agreed improvements (roadmap).
2. **`rooms-appendix.md`** — reference: zone schema, `roomzone`/`rz` builder verbs, mechanics
   table, render tokens, player verbs, permissions.
3. **`room-types.md`** — the composed type hierarchy, the type matrix, new types, migration.
4. **`room-mixins.md`** — the capability dictionary: every mixin + component + feature, with a
   worked example each (from the real cabin rooms) and `[BUILT]`/`[ROADMAP]` status.
5. **`room-recipes.md`** — assembling rooms from capabilities; worked recipes (Jacuzzi, Auria's
   Playroom, Shower, Play Pen, Cave Mouth).
6. **`maze-gating.md`** — the maze + the gate primitive; exact `maze` syntax; the fail-open rule.
7. **`gate-conditions.md`** — the condition catalogue (built gate types + proposed reveal conditions).

## Doc set — Characters (in progress)
- **`characters.md`** — overview & new-player flow: the OOC/account layer (café hub, roster,
  ograms-with-account-notify, consent defaults), the tutorial (replaces `forming`), default
  layers, the sheet/look rework, and the still-open social/identity half.
- **`character-zones.md`** — the spine: the typed hierarchical zone tree (base/outfit/accessories);
  zone *types* + the slot system; items-install-into-slots (generalizing `BodyModItem`);
  upgrades-valid-by-zone-type; covering-follows-tree; lock/key items (replacing plock/slock) +
  Durgin unlock; form-shift tiers.
- *(planned)* `character-emotes.md`, `character-consent.md`, `character-social.md`.

## How this fits the workflow
1. Cram ideas into the live game (trial by error).
2. Note rough ideas / experiments in `../testideas/`.
3. When something **works**, write its blueprint here.
4. When ready, build the fresh game from the blueprints — keep only what works, skip the rest,
   no stripping-out or working-around required.
