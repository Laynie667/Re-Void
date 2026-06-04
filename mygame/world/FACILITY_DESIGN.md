# The Facility — Realm Design Guide

The design bible for **The Facility**: a disconnected, gated grid realm and its
own in-game faction, built to process, breed, condition, and slowly break a
willing resident over a long progression. Companion to `CLAUDE.md`.

---

## 1. Vision

A numbered containment-and-processing complex — **backrooms liminality**
(humming sodium light, wrong-warm air, corridors that loop) fused with **SCP
clinical dread** (everything catalogued, contained, *documented*) wrapped around
a **breeding/dairy facility**. You don't visit it. You're **admitted**, you
**sign**, and the cycle takes it from there — dragging you room to room, milking
and breeding and conditioning you on a schedule that never lets you finish or
stay anywhere, looping until you're graded worthy to go deeper.

It is its own **realm** (disconnected rooms, area-tagged, waystone-gated) and its
own **faction** (a slow standing track that becomes your grade, your title, your
sheet). It is a **slow burn**: the descent is earned over many sessions.

**Core fantasy:** consensual non-consent. Total in-fiction helplessness and
inevitability, with an absolute OOC safety floor underneath (`escape`/`purge`).

---

## 2. Entry, return, and the floor

- **Entry:** a `HubWaystone` in housing + an `intake waypost` in the lobby with a
  hidden address. Speak the entry word in housing → dropped into Intake.
- **Return (gated):** the return waypost in housing starts with **no address**;
  saying anything is a no-op until `reveal_return()` activates it — i.e. until
  the facility decides you've earned the way home.
- **The floor (never gated):** `escape(me)` (home + purge) and `force_clear(me)`
  always work, unconditionally. This is sacred. See `CLAUDE.md §0`.

---

## 3. The rooms (current six; the sprawl extends from here)

| Room | Role | Key zones / mechanics |
|------|------|----------------------|
| **Intake (lobby)** | admission, the contract, the brand | counter (restrain), waystone, door, light; the contract on the counter |
| **Processing Floor** | milking + dosing | line (restrain), rigs (real milking); bench/rack/machine/cart furniture |
| **Breeding Pens** | bred by the animals | stalls (breeding stocks restrain), kennel; bull/boar/stallion/hounds NPCs |
| **Conditioning Cell** | the Process, brainwashing | cradle (restrain), dark; sound-eaten, the voice up close |
| **Dairy & Output** | her product, displayed | racks (milking), ledger; a shelf that's all her number |
| **The Pigsty** | the wallow, punishment/end-tier | wallow (seat), trough (seat); slopped, hosed, rutted |

Each room: full `desc` + `{zone:}` tokens, multi `study_details`, `handle`
interactions, room `ambient_msgs`, real installed mechanics, FacilityFurniture,
and FacilityAttendant/FacilityBeast NPCs.

---

## 4. The cycle — what each loop should feel like

Driven by `RealmCycleScript` (on the character, ~3 min/phase). On each tick it
**drags** her to the next room (real teleport with a "you don't get to walk it"
transition) and runs that room's themed scene. The ideal arc of one full loop:

1. **Intake / re-grade** — pulled back to presentation; a *Processing Review*
   set-piece fires if she's crossed a grade (witnessed, branded, re-titled).
2. **Milking Floor** — strapped in, milked for real (ml drained → banked), and
   mid-phase **dosed** (an experimental drug/procedure with a permanent effect).
3. **Breeding Pens** — bred by the animals actually in the room (real
   penetration engagement + `do_inseminate` deposit, broadcast with the hole),
   scene type rolled (single / DP / airtight / spitroast / knot-train / her own
   get) gated by what her holes can now take.
4. **Conditioning Cell** — the Process speaks to her real numbers, a trigger is
   reinforced, a degradation lands.
5. **Dairy / Output** — her quota board thrown in her face; what she's produced,
   shelved by number.
6. **Pigsty (on a slip)** — if she's forfeited her freedom, diverted down to be
   slopped and punished instead.

Underneath every phase: the **subliminal drip** (private), **slow conditioning
gain**, **slow faction standing gain**, and the occasional **special event**
(inspection / open-house / culling review / audit / buyer / restock).

A good cycle = legible (you always know which room and what's being done),
escalating (harsher as grade/holes/heat climb), and never resolved (dragged off
mid-use, every time).

---

## 5. Progression (the slow burn)

- **Conditioning** (`db.conditioning`) — brokenness. Staged effects: arousal
  floor → speech drift → trigger install → designation → **name loss** →
  self-mod lock → animal imprint. Tuned slow.
- **Faction standing** (`db.factions["The Facility"]`) — rank in the realm.
  Tiers: **Intake (40) → Breaking In (150) → Breeding Stock (400) → Broodmare
  (900) → Perfected Livestock (1800)**. Drives `title_faction`/grade/sheet.
  Perfected is dozens of hours deep. `standing` command shows progress.
- **Holes** — trained per-use; unlock knot → double → fist → prolapse, which
  unlock harder scenes. **Quotas** (per-species breeding + milk) with interest,
  ratchet, and an offspring spiral that moves the finish line.
- **Compliance** — defiance is punished and counts toward **freedom-forfeit**;
  earned back only by meeting every quota AND a long unbroken streak.

---

## 6. Improvements & goals (roadmap)

**High value, next:**
- [ ] **Room descriptions up to the witch_build/Helena bar** — richer, filthier
      prose per room and per zone; more `study`/`detail`/`handle` depth.
- [ ] **Cursed-item zone-installs** — items/injections that install REAL zones &
      mechanics on the *character* to *facilitate* scenes (a bred-ready womb
      zone, a milk-rigged chest, a locked-open hole, ownership/brand zones with
      enforced permanent descs). Facilitation, not the un-fun auto-process.
- [ ] **Real NPC behaviour** — attendants/handlers/animals acting through the
      game's `say`/emote/ambient systems (genuine actors, not narration) so
      witnesses see them act.
- [ ] **Deepen scene pools further** (every per-scene pool to 4–6 variants).

**Systems:**
- [ ] **Lineage/generations** — offspring breeding her produce next-gen get,
      accelerating, each raising quota more steeply.
- [ ] **Witness/other-player hooks** — others read the board, use her toward
      quota via `process <her> <action>`, say her installed triggers, sign on as
      handlers; other-livestock NPCs for comparison/ranking.
- [ ] **Earn-back economy / dedicated facility reputation tier names** on the
      global sheet line; a facility "status" room fixture / board updates.
- [ ] **Heat synced to the spiral**; **collar↔contract synergy**; **branding on
      milestones** (already partial); **self-writing addendums** (done).

**Sprawl:**
- [ ] More rooms + the **deep sub-levels** for Perfected stock; non-linear
      corridors that loop (backrooms); a multi-occupant **parlour/conveyor**.

---

## 7. Reset & cleanup contract (don't break this)

Everything the realm/facility installs MUST be undone by the reset path:
- `force_clear(owner)` — bulletproof, step-independent: clears all db state,
  stops `realm_cycle`/`perpetual_heat`/`body_processing`/milking scripts,
  removes facility piercings + freeform marks, restores name + title + consent,
  clears faction standing.
- `escape(owner)` — home + `run_facility_reset(purge=True)`.
- `teardown_realm(owner)` — deletes all `category="realm"`-tagged objects + realm
  rooms + housing waystone/waypost.
- `run_facility_reset(purge=...)` — normal leaves persistent marks (bleed-over);
  `/purge` is scorched earth. The OOC floor.

When adding ANY new persistent effect, add its teardown to **all** of the above.

---

## 8. Tone

Cold institution, warm cruelty, real degradation, inevitability — and the floor
underneath it all. Write it filthy. See `CLAUDE.md §0, §5`.
