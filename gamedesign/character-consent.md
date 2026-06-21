# Consent & Hardcore — the minimal toggle

*Design-from-scratch reference. Deliberately **minimal scope.** Consent is one toggle, hardcore is
one switch, and the OOC floor is a quiet fire-exit — always there, never advertised. Overview:
`characters.md`. The act framework that reads this: `character-emotes.md`.*

> **[BUILT]** live · **[SPLIT]** exists, reorganize · **[ROADMAP]** target.

## Design rule (read this first)
Consent here is **not** a per-act, per-zone permission matrix, and the floor is **not** plastered
across the fiction. The whole surface is:
1. A single **allow / block** stance toward interaction.
2. A **per-person** exception list on top of it.
3. A binary **hardcore** switch.
4. A quiet, always-working **escape**.

No "intimate gate vs. penetration gate," no consent-log walls, no immersion-breaking "⚠️ here's how
to escape" banners. If a design idea adds a gate or a disclaimer, it's wrong for this system.

---

## 1. Consent — one toggle + a name list  [ROADMAP — simplify what exists]
A character's stance is **allow all** or **block all**, with **named exceptions**:
```
consent allow            # anyone may interact
consent block            # no one may interact
consent allow <name>     # exception: let this person in (while blocking others)
consent block <name>     # exception: shut this person out (while allowing others)
consent                  # show current stance + exception list
```
That's it. The act pipeline's consent step (`character-emotes.md` §1, step 2) collapses to a
**single yes/no**: *may this actor interact with me right now?* — stance, then the name list
overriding it. No verb keys, no zone keys. Either someone can touch you or they can't; you can name
exceptions either way. **Account-default** is just the stance a new character inherits and can flip.

## 2. Hardcore — one switch  [ROADMAP — opt-in]
```
hardcore on    # immersion mode
hardcore off   # default
```
Binary. No tiers, no per-feature sub-gates. Its **only** effect: while on, `escape` stops doing its
*item teardown* (locks/marks/installed items persist as IC instead of auto-clearing). It **never**
changes that `escape` frees the **person** (see §3). Self-toggleable any time; flip it `off` and
`escape` does the full clean again — so the wipe path is never gated. Superuser purge ignores it.

## 3. The escape — quiet fire-exit  [BUILT — keep, don't advertise]
`escape`/`force_clear` (and the superuser purge) always end the scene, relocate, clear realm/facility
state, and free the **person** from anything that would trap them — **unconditionally, self-service,
never gated** behind a phrase, tier, debt, lock, staff, or payment. This is the one non-negotiable
(CLAUDE.md §0). What this doc adds is the *presentation* rule: it stays **quiet** — the command
exists and works; it is **not** narrated into scenes, not banner-warned, not stapled to every locked
door. A player who needs it knows it; everyone else never sees the seam. (Non-trapping consensual
items — a belt, a collar — come off IC via key / Durgin's unlock; the floor doesn't strip them, and
hardcore keeps them across an escape. None of that gates the person's exit.)

## Real subsystems this builds on / replaces
- **Builds on:** `consent.may` (becomes the single stance+list check), the existing block list,
  `escape`/`force_clear`/superuser purge (unchanged).
- **Replaces:** any per-verb / per-zone consent-key gating → one stance + name list; verbose
  in-fiction floor messaging → a quiet, unadvertised command.

## What to carry into the fresh build
- ✅ One allow/block stance + per-person exceptions; binary hardcore; the always-working,
  never-advertised escape.
- 🔧 Collapse the act pipeline's consent step to the single stance check; strip per-verb gating;
  remove immersion-breaking floor text from scenes/UI.
- ✂️ Per-act/per-zone consent matrices; consent-log walls; escape disclaimers plastered in-fiction.
