# Audit — Text Editor, Ograms, Factions (+ realm designation ideas)

A pass over the three systems for **integrity & integrations**, then **ideas**.
Severity: 🔴 bug that can bite · 🟠 fragility/footgun · 🟢 fine/observation.
Nothing here is changed in code yet — this is the review.

---

## 1. Text editor (`world/text_editor.py`)

Integrated into **7 callers** via `_enter_editor` + `_PENDING_SETTERS`:
`ogram_commands`, `builder_commands`, `character_commands` (×5), `freeform_commands`,
`womb_commands`. So any weakness here is felt everywhere.

### Integrity
- 🔴 **Setter lost on reload (systemic).** `_PENDING_SETTERS` is an in-memory module dict;
  the editor cmdset is `persistent=True`. After a `@reload` (or a crash) mid-edit, the buffer
  survives but the *save function does not* — so `:done` can't save. Only the `_room_field`
  path prints a helpful "target was lost" note; the others fall to "Unknown edit target." Every
  one of the 7 integrations inherits this. *Fix direction:* persist a **serializable** save
  descriptor (a registry key + args), not a closure; or, on reload, detect a stranded editor and
  tell the user the draft can't be saved and to re-open (better than a silent fail).
- 🔴 **Shared dynamic-target keys collide across callers.** Room edits register a **global**
  key — `EDITOR_TARGETS["_rdesc_dynamic"]` (also `_rentry_/_rexamine_/_rambient_dynamic`) — whose
  setter closes over a specific `room`. If two builders edit room descs at once, the second
  overwrites the first's setter, and the first builder's `:done` **saves to the wrong room.**
  *Fix:* key per-caller (`f"_rdesc_{caller.id}"`) or route through the per-caller `extra={"setter"}`
  path. (womb's `_womb_{zone}` has the same shape; its `lambda c: lines` getter also captures stale
  initial lines, lower impact.)
- 🟠 **`EDITOR_TARGETS` only grows.** Dynamic registrations are never removed — slow leak + stale
  closures. Cleanup on `_exit_editor` would tidy it.
- 🟠 **`mergetype="Replace"` strips *all* commands** (no `help`, no `look`). The new bare-word
  rescue + reconnect banner mitigate the "trapped" feeling, but a tiny allowlist (`help`, `look`)
  could be friendlier without losing the line-capture behaviour.
- 🟢 Buffer-on-db survival, the new exit synonyms, bare-word rescue, and reconnect reminder are all
  good now. `:done/:cancel` routing is solid.

### Ideas
- **`:undo`** (pop last line), **`:swap <a> <b>`**, **`:move <from> <to>`** — quick line ops.
- **`:wrap`/`:format`** — soft-wrap preview at the client width so people see how a desc will read.
- **Colour preview** — render the buffer with ANSI applied on `:show` (it's shown raw now).
- **Per-caller save descriptors** (the real fix for the reload gap) — also unlocks **draft recovery**:
  "you have an unsaved draft for X — `:resume` or `:discard`."
- **Live char count** vs the target's limit (ogram has a 4000 cap that's only checked at save).

---

## 2. Ograms (`commands/ogram_commands.py`)

Persists to a Django model (`web.mail.models.OgramMessage`); delivered on login via
`deliver_ograms(account)` from `Account.at_post_login`. Couriers: Seraphine/Calix/Vesper
(arrival pools now 8 each). Allowance ograms deposit **15 shards** (display and deposit agree ✓).

### Integrity
- 🔴 **Compose-then-reload loses the send** — same root as editor #1 (`_open_editor` stashes the
  send closure in `_PENDING_SETTERS`). Reload mid-compose → `:done` can't send the ogram.
- 🟠 **`auto_quit=False` EvMenu** relies on every node carrying `q/quit/cancel`. They do today, but
  it's a standing footgun — one node added without it = a trap. A menu-wide abort would be safer.
- 🟠 **Affection/anon/gender drafts live on `caller.db._ogram_draft`** — fine, but never expired; an
  abandoned draft lingers. Low impact.
- 🟢 Delivery, email notification, anonymity, shard deposit, and the `ImportError` guards are clean.

### Ideas
- **Reply / threading** — `ogram reply <#>` so an exchange reads as a conversation.
- **More message types** — already has message/emote/affection/invite/staff/allowance; add
  **contract/summons** (a facility intake invite that opens the contract), **gift** (attach shards),
  **bounty** (post a job other players can claim).
- **Courier flavour by relationship/standing** — pick the courier or their tone from the sender's
  faction or the pair's history; deepen the allowance grope/no-grope pools the same way the arrivals
  were deepened.
- **Scheduled / timed ograms** — "deliver at next dawn," "deliver when they enter <realm>."
- **In-world reading UI** — an `ograms` command to re-read delivered ones (currently "full mailbox on
  the website").

---

## 3. Currency overlap — the cross-cutting one 🟠

There are **two unrelated currencies**:
- **Shards** (`typeclasses.economy`) — the **game-wide** wallet: `db.shards`, daily passive cap,
  `transfer_shards`, logged mutations, fed by allowance ograms. The real economy.
- **Scrip / `facility_credits`** (`world/economy.py`, mine) — **facility-internal**: earned off her
  body, spent on the block/floor, the house treasury, debt/indenture.

They don't talk. That's defensible (realm-local vs global), but for realm designation it's a
decision to make on purpose, not by accident. **Options:** (a) keep separate, and make scrip a
*realm-scoped* currency with an explicit exchange at the facility boundary; (b) make the facility
house-treasury denominate in **shards** so takings are real money; (c) generalise "scrip" into a
**per-realm currency** any future realm/faction can mint. (c) pairs naturally with factions below.

---

## 4. Factions (`world/factions.py`) — and realm designation

### Current state
- Hardwired to **one faction, The Facility**: `_FACILITY_TIERS`, `_GAIN`, title slots
  (`"of The Facility"`) are all Facility-specific.
- `character.db.factions` is a `{name: int}` dict that *can* hold many factions, and
  `add_standing(faction=...)` accepts any name — but only The Facility has tiers/titles/grades.
  Everything else is a bare number shown raw by `standing`.
- 🔴/design **No realm↔faction link.** Realms (`realm_build`) are per-character instances tagged
  `the_facility`/area `"The Facility"`. Nothing records *which faction owns/runs a realm*, and there's
  no faction object to own one. So "designate this realm to a faction" has nowhere to write to today.

### Ideas — toward designating realms & factions
- **Data-driven faction registry.** A `FACTIONS = {key: {name, colour, tiers, title_prefix,
  home_areas, leader_npc, currency, ...}}` table (or a `Faction` script/object). Make The Facility the
  first row, not the hardcode — `factions.py` becomes generic.
- **Realm ownership tag.** Stamp each built realm/area with an owning faction (`area_faction`), and a
  registry `faction -> [areas/realms]`. `build_realm`/a `designate <realm> <faction>` staff command
  writes it. Then "where"/sheet/standing can show whose territory you're in.
- **Generalised tiers & titles.** Lift `_FACILITY_TIERS`/`_apply_*_title` to read from the faction
  registry so any faction grants its own grades/titles (`of The <Faction>` + suffix).
- **Membership & rank.** Standing → rank within a faction; gate realm access / commands / prices by
  rank (e.g., only members above X enter the Deep Stock, or buy on the block).
- **Faction treasury = the currency hook.** My house treasury is really a proto-faction-treasury;
  generalise it so each faction pools dues/takings (in shards or its own scrip per §3), and spends on
  upgrades/bounties — exactly the reinvestment ladder, but per faction.
- **Inter-faction standing.** Rivalries/alliances: gaining with one faction can cost another; realm
  border effects; safe-conduct vs hostile-on-sight by standing.
- **Faction-flavoured ograms** (ties §2): couriers, invites, and summons keyed to the faction —
  a Facility intake-summons ogram that opens the contract is the obvious first one.

### Suggested first slice (when we build it)
1. Make `factions.py` **data-driven** (registry), Facility as row 0 — no behaviour change, just
   generalised.
2. Add **realm/area → faction ownership** + a staff **`designate`** command.
3. Then layer rank-gating and a per-faction treasury on top.

---

## Quick-fix candidates
1. ✅ **DONE** — Per-caller dynamic editor keys (`_rdesc_{caller.id}`, `_womb_{caller.id}_{zone}`):
   the cross-builder save-to-wrong-room bug is closed.
2. ✅ **DONE (ogram)** — Reload-safe save: the ogram now uses a `_ogram` setter_key that rebuilds the
   save from `db._ogram_draft` (no closure to lose), so composing-then-reload no longer eats the send.
   Other closure callers now get a real recovery message that **shows the buffer back** so text isn't
   lost. (A fully serializable descriptor for *every* caller is still the long-term ideal.)
3. ✅ **DONE** — `_exit_editor` now pops per-caller dynamic targets + the pending setter (no leak).
4. 🟠 Menu-wide abort for the ogram EvMenu — still open (every node carries `q/cancel` today, so it's
   not currently a trap; deferred).

## Naughty additions (done)
- Affection ograms grew from 4 → **9** types: `kiss`, `french_kiss`, `hug`, `grope`, plus **`nibble`,
  `tease`, `worship`, `claim`, `ravish`** — each with 3 courier-delivered variants in the house voice,
  graded from teasing to filthy, wired into the affection menu (claim/ravish flagged red).
