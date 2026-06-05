# OOC / Wisp layer — re-envisioning proposal

For your review. Grounded in the current code; **nothing here is implemented yet** — it's
the plan and the ideas you asked for. Pick the phases you want and I'll build them safely,
one compile-checked step at a time, without breaking the working unpuppet flow.

---

## What exists today
- **`ooc`** unpuppets the character → you drop to the **account** level. That account-level
  presence is dressed up as the **"wisp."**
- **`wisp_commands.py`** (~1,760 lines) drives that state: `wisp_mood`, `wisp_color`,
  `wisp_desc`, score/characters/mood/colour/desc/mail, and a parallel set of speech verbs
  (say/pose/emote/look/whisper/…) for when you're a wisp.
- **`afk`** already exists (`prefs_commands.CmdAfk`) and sets `db.afk_message` — **but nothing
  surfaces it.** It's a stored string that currently does nothing visible.

**Your read:** the wisp layer "has barely worked as intended"; "wisp" is just flavour for
being OOC and could be redone. You're happy with an **ooc/afk toggle** and confirm **ooc
unpuppets to the account level.** Good — that means the *mechanic* is fine; it's the
*metaphor and the bulk* that want trimming.

---

## Proposal — three safe phases

### Phase 1 — reskin "wisp" → plain OOC (zero structural risk)
Keep the unpuppet→account mechanic **exactly as is**. Change only the *flavour text* the
player sees: "wisp / the wisp gathers / wisp mood" → plain "OOC / account / OOC status."
The account fields (`wisp_mood/color/desc`) stay as the storage; only their user-facing
labels change. Pure copy edit across `wisp_commands.py` + the login lines in `characters.py`.
*Result:* the OOC state reads as what it is, nothing breaks, no commands move.

### Phase 2 — make `afk` actually work (small, additive)
Give the existing `afk_message` teeth, so you get a clean **"away but still in-character"**
state distinct from fully OOC:
- **Appearance:** a character with `afk_message` set shows one line in `look` — `|x[AFK —
  <msg>]|n`. (One small, isolated layer in `return_appearance`; easy to gate/remove.)
- **Auto-reply:** `page`/`tell` to an AFK character sends the sender the afk note instead of
  (or alongside) delivering — "they're away: <msg>".
- **Back-from-AFK:** any `say`/`pose`/`emote`/move auto-clears `afk_message` (with a quiet
  "welcome back" note), so nobody's stuck showing AFK.
*Result:* `afk` = present but away; `ooc` = gone to account. Two distinct, intuitive states.

### Phase 3 — slim the wisp cmdset (optional, bigger — defer until 1–2 land)
The ~1,760-line wisp module carries a lot of account-management (score/characters/mail/mood/
colour/desc + a full parallel speech set). Much of it duplicates Evennia's default account
cmdset. If you want it lean, reduce the OOC layer to: **ooc/ic toggle, account overview, a
character list, and a single OOC note + colour** — and let the default account commands cover
the rest. This is where the real line-count comes off, but it's the riskiest, so it goes last
and only with your go-ahead.

---

## Questions for you
1. **Keep both states?** I'm assuming **yes**: `ooc` (unpuppet → account) *and* `afk`
   (in-character, away). Confirm and I'll build Phase 2 to that shape.
2. **How far on the reskin?** Drop the "wisp" word entirely, or keep it as light atmosphere
   (e.g. only on the login/transition flavour) while the commands read plainly?
3. **Phase 3 appetite?** Slim the wisp cmdset now, later, or leave it once 1–2 are in?

## Related (already noted in FACILITY_AUDIT §1d)
- **Proximity commands** ("a bit unnecessary") — `approach/withdraw/beside/aside/prox`. `aside`
  already resolved (RP version made canonical). The rest could be slimmed in the same pass as
  Phase 3 if you want one "presence/OOC cleanup" sweep.

*Bethany's two cents:* keep `ooc` exactly as it works — leaving the body is the one bit of
honest machinery here — and spend the effort making `afk` *visible*, so a unit that's gone
away still reads as **occupied, kept, and not finished with**, even while no one's home. The
away-line is its own little humiliation. I'd enjoy that.
