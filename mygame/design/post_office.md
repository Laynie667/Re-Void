# The Postal Office — Design Reference
*Room built. NPCs pending. Do not spawn until scripts are written.*

---

## Status

| Element | Status |
|---|---|
| Room dug (#32) | ✅ Done |
| rdesc / rentry / rexamine | ✅ Done |
| rtime layers | ✅ Done |
| rweather layers | ✅ Done |
| Ambient pool + AmbientScript | ✅ Done |
| Seraphine NPC | ⏳ Pending |
| Calix NPC | ⏳ Pending |
| Vesper NPC | ⏳ Pending |

---

## Location

Dug west from the Wayfarer's Hall (#2). Exit aliases: `west`, `postal office`, `post`, `post office`, `ogram office`.

---

## The NPCs

These three are already fully characterized in `commands/ogram_commands.py` — their appearance, personality, and delivery behavior are all established there. The in-room NPC versions should match that source exactly.

### Seraphine
**Station:** Left end of the counter — warmest, slightly cluttered workstation.
**Appearance:** Crimson-skinned tiefling woman. Small swept-back horns. Expressive tail. The particular poise of someone who has heard every kind of secret and found most of them charming rather than shocking.
**Personality:** Warm, knowing, unhurried. Entirely at home in other people's private moments. Will look up when someone enters and take them in with obvious interest.
**Look desc:**
```
Seraphine occupies the left end of the counter the way she seems to occupy most
spaces — entirely, and without apology. Crimson-skinned, small swept-back horns,
a tail that moves with an expressiveness she doesn't bother to suppress. She is
reading the front of a sealed letter with the expression of someone who could
absolutely open it if she wanted to and has chosen, generously, not to. She looks
up when the room changes. She takes you in with the particular warmth of a woman
who has heard every kind of secret and found most of them charming rather than
shocking.
```

---

### Calix
**Station:** Center of the counter — immaculate workstation, everything at a right angle.
**Appearance:** Deep charcoal-skinned tiefling man. Ram horns. Broad-shouldered. Built like someone designed for considerably more demanding work than this.
**Personality:** Few words. Absolute discretion. Unhurried solidity. Glances that hold one beat longer than necessary, then return to work as though you imagined the extra beat.
**Look desc:**
```
Calix stands at the center of the counter with the unhurried solidity of something
built to last. Deep charcoal skin, ram horns, the broad-shouldered patience of a
man who has carried stranger parcels than this in worse weather and arrived looking
entirely unbothered. He is sealing a letter with three precise impressions of the
stamp — no more, no fewer. He glances up without expression. The glance holds a
beat longer than necessary. He returns to his work as though you'd imagined the
extra beat, which is probably what he intended.
```

---

### Vesper
**Station:** Far right of the counter — minimal workstation, only the bare essentials.
**Appearance:** Opalescent-skinned tiefling of undisclosed nature. Swept-back horns that shift between sharp and softer depending on the light. Eyes that change color: silver, then violet, then something without a name.
**Personality:** Speaks rarely. Deliberately unreadable. Can be flustered by direct attention — will find something nearby to focus on intently. Their nature has never been stated and they prefer it that way.
**Look desc:**
```
Vesper is at the far right of the counter, their attention apparently absorbed by a
sorting task that doesn't seem to need quite this much focus. Opalescent skin.
Swept-back horns that catch the lamplight differently every time you look. Their
eyes, when they briefly track across the room, are silver — then a color that sits
somewhere between violet and something that doesn't translate. They are holding a
letter marked |xAffection — Grope — Anonymous|n with the focused neutrality of
someone who processes these regularly and has developed a professional relationship
with the fact.
```

---

## Notes for Implementation

- All three share the same physical space. Only one or two may be "present" at a time depending on future scheduling logic, or all three can be present simultaneously.
- They do not need dialogue trees at first — a `look seraphine` / `look calix` / `look vesper` with the above descs is sufficient to establish them.
- Longer term: could tie them to the ogram delivery system so they "leave" when carrying a message and "return" after delivery.
- Their ambient contributions are already seeded in the room's ambient pool and reference all three by name.

---

## Spawn Command (when ready)

To be written. Will follow the same pattern as `world/durgin_spawn.py`.
Reference file: `commands/ogram_commands.py` for full character details.
