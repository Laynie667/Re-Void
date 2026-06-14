# Seraphine ↔ Bethany — the peerage, unbirthing, and the nested-passenger transfer

*Design + decisions for the facility ↔ post-office interpersonal layer. Answers the user's
open questions with recommendations (Bethany/the user have final say; these are the proposed
canon). Build hooks at the end.*

---

## 1. The relationship (canon)

Bethany owns everyone and submits to no one — with exactly **one** exception, and it's
**Seraphine**. They are *peers*, the only equals in each other's worlds: two warm-cruel
proprietors who collect and keep people, who recognise their own kind across a counter, and who
have a standing, knowing, decades-deep arrangement that neither calls love and both protect.

- **Seraphine is the only person Bethany lets fuck her pussy.** Bethany — the monstrous triple-
  cock futa who tops the entire facility — *opens* for exactly one person. It is the physical
  expression of the peerage: the one place the owner of everything is, briefly, not the owner.
  It is rare, deliberate, and the most intimate thing in either of their lives.
- **Seraphine as facility buyer.** Seraphine visits the facility's auctions and deals directly
  with Bethany for choice product — especially Deep Stock and bred lots — which gives the
  post-office clerk a logistics reason to exist (she's a *buyer*) and ties the two locations.
  Her signature acquisition is **forced adoption / unbirthing**: she takes her purchases home
  *inside her*.

## 2. Does Bethany's (DEVOTION-laced) cum affect Seraphine? — DECISION

**Recommendation (proposed canon): Seraphine is the one it doesn't *own*.** Years of taking
Bethany's laced loads — plus her own seasoned nature (a woman who has heard every secret and
been changed by none) — have made her **immune to the DEVOTION's will-binding**. It still
*affects her body* (the heat, the craving, the high — she enjoys it, chases it, is not made of
stone) but it **never touches her will**. She remains entirely herself, every time.

This is precisely *why* Bethany trusts her, deals with her, and opens to her: Seraphine is the
only being who can take everything Bethany is and walk away still Seraphine. The immunity is the
foundation of the peerage. (Alt option, if preferred: it affects her *a little*, a shared secret
softness only the two of them know — but the immune-peer framing is the recommendation; it's
hotter and it explains the trust.)

→ **On the PLAYER, Bethany's cum always lands in full** (cumflation + DEVOTION), regardless of
which host the player is inside. Only Seraphine is immune; the player never is.

## 3. The nested-passenger transfer mechanic — DESIGN

A "passenger" system built on the existing **WombRoom** (`typeclasses/womb_room.py` — an
interior room located inside a host, with flood states). Two interior types:
- **womb** (gestation passenger space — exists),
- **balls/testes** (a breeding-passenger space — NEW interior, cumflation/holding).

**Transfer rules (the user's scenarios, ruled):**
- **Player in Seraphine's balls + Seraphine inseminates Bethany → player is DEPOSITED into
  Bethany.** The act moves the passenger host→host (Seraphine's balls → Bethany's womb). The
  player rides the load across.
- **Player in Seraphine's womb + Bethany cums in Seraphine → player is COVERED in Bethany's
  cum.** Bethany's laced load floods Seraphine's womb where the player rides; the player gets the
  full cover (cumflation + DEVOTION reaching them *through* Seraphine), even though Seraphine
  herself is immune. The membrane doesn't protect the passenger; only Seraphine's will is immune.
- **Bethany's cum effect resolves per §2:** full on the player, body-only on Seraphine.

**Implementation hooks (when built):**
- New `balls`/`testes` WombRoom interior type (mirror the womb interior; flood = "load").
- `transfer_passenger(passenger, from_host, to_host, via=act)` helper — re-homes the passenger
  interior-room's location from one host to another on the triggering act.
- `cover_passenger(passenger, fluid, laced=True)` — applies the cover/DEVOTION to a passenger
  when their host's interior floods from an external deposit.
- All passenger state in FACILITY_FLAGS so the floor clears it.

## 4. §0 floor (load-bearing — VERIFIED)

`escape()` relocates via `owner.move_to(housing, quiet=True)`, which bypasses `jump_protected`
(that flag only locks the player jump/teleport *command*, not a forced engine move). So escape/
force_clear **always** pull a passenger out of any host's womb/balls, regardless of nesting.
**Build requirement:** add an explicit belt-and-suspenders unbirth-on-escape in the captive-
carry code anyway (eject any passenger to housing first), and register every passenger flag in
FACILITY_FLAGS. The unbirthing/captive-carry can be as inescapable as desired in-fiction; the
floor stays unconditional.

## 5. The post office needs the same cinematic upgrade

The post office (Seraphine/Calix/Vesper, the clerk menu, officiating) should get the same
`bx_*`-style cinematic, choice-driven, state-aware scene treatment the facility's 14 rooms got:
- **Officiating as a scene** (drafting → the clause-kissing → the seal), each clerk an actor.
- **Seraphine's forced-adoption contract** as a scene (the womb hidden under the foster paperwork).
- **Per-clerk scenes** in their pocket rooms (the toybox, the nest, the keeping-room).
- Reuse the scene engine (`start_scene`, `scene_flags`, node `then`, `_state_tags`).

## 6. BUILT this pass

- **The Seraphine scene** (`se_*`, `scene seraphine`): her visit to the facility to collect her
  purchase — the Bethany↔Seraphine peerage on display (the only one Bethany opens to), the player
  handed over, the unbirthing carry-home. Real `seraphine_takes` ownership transfer
  (`seraphine_owned` flag, floor-clearable) + devote; the §2/§3 rulings embodied in the prose; the
  deep passenger-transfer subsystem (§3) gestured at and queued.

## 7. Queued

- The passenger-transfer subsystem (§3) as real WombRoom mechanics.
- The post-office cinematic upgrade (§5).
- Facility **Events** + the **scene-flow controller** (still on the facility plan).
