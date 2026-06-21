# Characters — the social & identity half: bonds, ownership, honorifics, titles

*Design-from-scratch reference. The identity-and-bonds half of a character: who you are to others
(relationships, ownership), what people owe each other (honorifics/nicknames), and how rank/standing
read out (titles). **Most of this is already built and deep** — this captures it and notes the few
additions you asked for. Overview: `characters.md`. Consent stance: `character-consent.md`.*

> **[BUILT]** live · **[SPLIT]** exists, reorganize · **[ROADMAP]** target.

## The idea
Relationships are a **tier spine** every other system queries: `tiers_of(viewer, target)` →
`self / owner / lover / family / faction / hostile / all`. Bonds are **offered between players and
accepted** (consensual by default); **owners can impose** the on-theme ones; **NPCs (Bethany,
Seraphine) tie into the exact same spine** — an NPC owner is just an `owner`-tier holder. On top of
the spine ride **honorifics** (what you must call someone present who holds a claim over you) and the
**multi-slot title**. The OOC floor reverts *forced/imposed* ties and leaves *mutual* ones alone.

---

## 1. Relationships — the tier spine  [BUILT — `world/relationships.py`]
`tiers_of(viewer, target)` resolves to a set drawn from three sources: factions (`faction`,
`hostile`), ownership (`owner`), and explicit links (`lover`, role-granular `family`). Family is
**role-granular** (mother/father/sire/dam · daughter/son/get · sibling) and the **reciprocal is
auto-written on the other party, gendered by their pronouns** — core to lineage/incest play. Bonds
are mutual via `offer / accept / reject`; `clear_forced` drops only *forced* ties (the floor hook).

## 2. Ownership — player-over-player as the default, NPCs tie in  [BUILT]
Ownership is the `owner` tier sitting on the spine: an explicit link, the facility owner-of-record,
or a faction owning its stock (Bethany over her line). **Multi-owner** is supported. Player-over-
player ownership is the **default model**; NPC owners use the identical path.

**The unified bond verb [BUILT — `relate`, generalizing `offer_relation`]:** one command offers
every bond, with a **duration switch**:
```
relate <who> = <bond>            # default: permanent, mutual (target must accept)
relate/temp <who> = <bond> <dur> # time-limited (30m / 2h / 3d / 90s); auto-expires
relate/perm <who> = <bond>       # explicit permanent
relate/accept <who> / relate/reject <who>      # the target's response
relate/force <who> = <bond>      # owner-imposed (forced; floor-reverted)
```
- **Bonds:** `own` / `slave` / `pet` (the `owner` tier with a stored **flavour** that seeds the
  default honorific/title) · `lover` · family roles (`mother`…). One verb, the relationship type as
  the argument. *(`faction` invite-at-rank is still ROADMAP — the faction system owns that path.)*
- **Consensual by default:** player→player bonds require the target's `accept` — and, per
  `character-consent.md`, persist through `escape` as normal IC state (a consensual collar isn't a
  trap). They come undone by mutual `clear`, not the floor.
- **Imposed path (on-theme):** an existing **owner** (player or NPC) may `relate/force` the ownerly
  bonds — family roles **and** own/slave/pet — stored `forced=True`. **The floor reverts every
  forced/imposed tie** (`clear_forced`); mutual ties stay.
- **Temp vs perm:** a temp bond stores `expires_at` on the relationship entry; `tiers_of`/
  `_is_owner_of` ignore it once expired (read-time), and `prune_expired` tidies storage lazily.
  Perm bonds (the default) carry no `expires_at` and behave exactly as before.
- **NPCs tie in:** Bethany/Seraphine own via the same `owner` tier and the same impose/force path —
  no parallel NPC-ownership system. This is *why* the player-over-player default matters: build it
  once, NPCs inherit it.
- **Ties to the world layer:** body-ownership (this `owner` tier) is the *body* half of the
  world-layer **ownership-transfer/seizure primitive** (`world-layer.md` §6a) — same backed-up,
  floor-reversible mechanism as housing/waypost/lineage. Document them as one.

## 3. Honorifics & nicknames — what people call each other  [BUILT enforcement → ROADMAP: the setters]
Three distinct things, kept simple:
1. **Personal nickname (your private view) [ROADMAP].** What *you* call someone — a per-viewer alias
   shown only to you (`nick <target> = <name>`). No consent needed; it's your own display. (Builds on
   the existing rp-name alias registration.)
2. **Imposed honorific (what your owned / lower-rank must call you) [BUILT].** Already exists as a
   **standing rule** an owner sets:
   ```
   rule/add <who> = honorific honorific:Mistress
   ```
   Setting it needs authority over the target (`consent.may(you, them, "rule.set")` — owner, or self
   on self). It's **enforced by the speech filter** (the holder's token must appear; consequence is
   `block` / `punish` / `notify`, with miss-escalation), and **the OOC floor wipes all rules.**
   `required_address` already picks the highest-priority present claim-holder (owner > lover > family
   > faction) and the token owed. **This is the contract-style enforcement you wanted — it's built.**
   **[BUILT] front-end:** `honorific <who> = <token>` (alias `address`) wraps the rule with the soft
   `notify` default — `honorific/clear <who>` removes it, `honorific <who>` shows what's owed; same
   authority check (`rule.set`/owner/self). Accepting a `slave`/`pet` ownership bond now suggests
   setting one. *Still ROADMAP:* fully auto-seeded per-owner defaults.
3. **Faction-rank honorifics [ROADMAP, hooks exist].** Lower members owe rank-holders a faction
   honorific — the `faction` tier is already in the address priority; wire a faction's rank ladder to
   supply the token.

**Enforcement philosophy (consistent with `character-consent.md`):** honorifics are **opt-in via the
rule/contract** an owner sets over someone they have authority over, **default consequence is the
soft `notify` nudge**, the harsher `block`/`punish` are deliberate per-rule choices, and **the floor
wipes all of it**. No global gate, nothing plastered on players who never signed up.

## 4. Titles — the multi-slot identity line  [BUILT — `characters.py`]
A title assembles from slots: `prefix / interfix / level / faction / realm / suffix` + `titles_earned`,
composed by `get_full_title()`. **Derived** slots update automatically — `level` from the social tier
(§5), `faction` from rank, `realm` from residency. **Awarded** slots are hand-granted (`titles_earned`,
`prefix`/`suffix`). Document the derived-vs-awarded line so the fresh build keeps it clean.

## 5. Standing, rank & the social tier  [BUILT — `factions.py` + `db.ln`]
`factions.py`: numeric **standing/rep**, named **rank ladders** (custom per faction), advance methods
(rep / exp / granted), residency, and faction-vs-faction relations (enmity → the `hostile` tier and
the Facility's title/grade). Separately, **`db.ln`** is a global social score feeding only the
`title_level` slot. **Open question (don't assume):** `ln` is a second reputation track parallel to
faction standing — decide whether it earns its keep or folds into faction standing for the fresh
build, rather than silently carrying a redundant meter.

## 6. One assembled view  [PARTLY BUILT — `relate` / `rel`]
The relationship view (`relate`, alias `rel`) joins bonds + ownership, and now **faction
standing/rank** too (read-only, defensive). Still ROADMAP: the honorific you owe to anyone
**present** right now.
**Known gap (your call):** `set_owner` stores the link only on the *owner's* side, so the **owned
party's `relate` view doesn't list who owns them** (ownership still works everywhere else — consent,
honorifics, `tiers_of` — via `_is_owner_of`; only the owned-side display is blank). Fixing it means
a two-sided owner link, which touches the floor/contract revert paths — a deliberate change, not a
blind one.

## Real subsystems this builds on
- `world/relationships.py` (the tier spine, offers/accept/force, `clear_forced`, honorific resolver
  `required_address`/`present_superiors`), `world/rules.py` + `commands/rule_commands.py` (the
  honorific standing-rule + authority check), `world/speech_filters.py` (honorific enforcement +
  escalation), `world/factions.py` (standing/rank/title), `characters.py` (`get_full_title`, the
  title slots, `db.ln`), the contract `binding_effects` (carries honorific/rule clauses), the
  world-layer ownership-transfer primitive (`world-layer.md` §6a).

## §0 OOC floor
`escape` frees the person and `clear_forced` reverts every **forced/imposed** bond, rule, and
honorific; **mutual, consensually-accepted bonds persist as IC** (released by mutual `clear`, not the
floor) — same line as a consensual collar in `character-consent.md`. Nothing here gates the exit.

## What to carry into the fresh build
- ✅ The tier spine; player-over-player ownership as the default with NPCs on the same path; the
  unified `relate [/temp|/perm|/force] <who> = <bond>` verb (own/slave/pet/lover/family) with expiry
  — **built**; the honorific standing-rule + speech-filter enforcement; the multi-slot title; faction
  standing/rank.
- 🔧 Build: the `faction` bond (invite-at-rank); personal `nick`; faction-rank honorific tokens;
  the assembled `sheet/relationships` view. *(The `honorific` front-end is now built.)*
- ✂️ Decide `db.ln`'s fate (fold into faction standing or keep) — don't carry a redundant meter blind.
