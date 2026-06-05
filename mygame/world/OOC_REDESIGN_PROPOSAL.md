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

## Where things actually live (and your keepers are safe)

I traced the three you named — **none of them are wisp/account flavour; they're all
character-level and untouched by any OOC rework:**

| Thing | Lives in | Level | Verdict |
|---|---|---|---|
| **`sheet`** | `character_commands.py` (`CmdSheet`) | character | ✅ **Keep, untouched** |
| **`portrait`** | `character_commands.py` (`CmdSetPortrait`) | character | ✅ **Keep, untouched** |
| **say/pose mood-colour** | `rp_commands._mood_color(char)` reads `char.db.mood` via `MOOD_COLOR_MAP` (`social_commands`) | character | ✅ **Keep, untouched** |

So the per-player colour on your say/pose text comes from the **character's** `db.mood`, *not*
the account's `wisp_mood`. The account has its *own* separate `wisp_mood`/`wisp_color` that
only tints the OOC presence text — a different thing entirely. Reworking the wisp layer can't
touch your IC sheet, portrait, or speech colours.

## Keep / cut triage for the account layer (`typeclasses/accounts.py`, 726 lines)

**✅ KEEP — real account management (not "wisp flavour", genuinely useful):**
- `consent_flags`, `consent_grants` (account-level consent)
- `block_list`, `friends`, `alert_on_friends`
- `adult_verified` / `adult_verified_at` (gating)
- `mail_inbox`
- `channel_colors`, `muted_channels`, `dnd`, `highlight_keywords`, `output_filters`,
  `custom_prompt`
- `tutorial_stage` / `tutorial_complete`, `discoveries` (onboarding)

**✂ CUT / SIMPLIFY — the over-built "wisp-as-a-creature" cosmetics (the part that "barely
worked"):**
- `wisp_size`, `wisp_movement`, `wisp_signature`, `wisp_sound`, `wisp_ambient_pool`,
  `wisp_haunt`, `wisp_revealed_to`, `wisp_name_display`, `custom_wisp_name` — the ethereal-
  creature dressing. Little/none of it pays off.
- `wisp_location`, `wisp_visible`, `wisp_preference` — the "your OOC self wanders the grid as
  a visible presence" idea. This is the bit that didn't work; OOC should be a menu/account
  screen, not a roaming grid entity. **Strongest cut candidates.**
- `wisp_mood`, `wisp_color`, `wisp_desc` — reduce to a **single OOC note + colour** (or drop
  entirely), since the *character* mood already colours all your IC text. Only keep what tints
  OOC-channel/presence text, if you want that at all.

**Net:** keep the account doing real account things (consent/block/friends/mail/channels/
verification/onboarding); strip the "wisp is a little ghost that drifts the map" layer; and
let `ooc` simply mean "you're at the account screen." That alone removes most of the
"barely worked" surface area, and it can't affect sheet / portrait / mood-colour.

---

## Original three-phase plan

> **Status note (honest):** Phase 2 (afk) is **done** — it's purely additive and safe.
> Phases 1 & 3 + the roaming-ghost cut all touch **`at_post_login` / the unpuppet flow**,
> which I cannot run-test in this sandbox. The reskin and the roaming removal are *coupled*
> (you can't relabel "you drift into the world" as "you're at the account level" while the
> code still drops you into a room), so they should land together, with a live login test.
> I will not ship blind changes to the login path. Give the word when you can test a build
> and I'll do Phases 1+3 + the roaming cut in one reviewed step.

### Phase 1 — reskin "wisp" → plain OOC (zero structural risk)
Keep the unpuppet→account mechanic **exactly as is**. Change only the *flavour text* the
player sees: "wisp / the wisp gathers / wisp mood" → plain "OOC / account / OOC status."
The account fields (`wisp_mood/color/desc`) stay as the storage; only their user-facing
labels change. Pure copy edit across `wisp_commands.py` + the login lines in `characters.py`.
*Result:* the OOC state reads as what it is, nothing breaks, no commands move.

### Phase 2 — make `afk` actually work (small, additive) — ✅ DONE
**Shipped.** `afk_message` now has teeth, all additive (no login-path risk):
- `afk <msg>` sets it + a timestamp and announces to the room ("steps away — present, but
  not answering"); `afk/clear` clears it + announces "is back".
- `look <char>` shows `|x[AFK — <msg>, Nm]|n` under the name (others *and* self).
- `page`/`tell` to an AFK character auto-replies the sender `(X is away: <msg>)`.
- AFK **auto-clears on activity** — say / pose / emote / move all drop it (with a quiet
  "is back"), via a new `Character.clear_afk()` / `is_afk()` / `afk_line()` helper set.

So `afk` = present-but-away (in-character); `ooc` = gone to account. The two states are now
cleanly distinct, which was the toggle you wanted.

### Phase 2 (original spec) — make `afk` actually work (small, additive)
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
