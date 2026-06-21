# Gate / Reveal Conditions — the catalogue

*Companion to `maze-gating.md` and `rooms-and-roomzones.md`. The condition types a gate/reveal
can check. **[BUILT]** = usable on maze solutions today. **[ROADMAP]** = proposed for the
generalized Reveal/Gate primitive (details/handles/studies/mechanics/exits).*

> **Universal rule: every condition FAILS OPEN.** Unknown type, missing stat, or any error →
> the gate opens / the thing is revealed. A gate is a *bonus lock*, never a trap. (§0.)

---

## A. Implemented — maze solution gates  [BUILT]
Set with `maze gate <name> = <type> [<min>]`. Checked by `MazeRoom._gate_ok`.
Stored as `solution["gate"] = {"type": <type>, "min": <number>}`.

| type | reads | opens when | min? |
|---|---|---|---|
| `conditioning` | `db.conditioning` | `>= min` | yes |
| `regression` | `db.regression` | `>= min` | yes |
| `devotion` | `db.bethany_devotion` | `>= min` | yes |
| `standing` | `db.facility_standing` | `>= min` | yes |
| `quota` | `gang_breeding.quota_met(caller)` | quota met | no |
| `stat` | any `db.<attr>` (gate's `attr`) | `>= min` | yes |
| `flag` | any `db.<flag>` (gate's `flag`) | matches `value` (default: truthy) | no |
| `time` | `gametime` period and/or season | matches `period`/`season` | no |
| `weather` | `weather.get_weather()` | matches `state` | no |
| `none` | — | (clears the gate) | — |

`stat` generalizes the four hardcoded meters above to **any** numeric attribute
(`{"type":"stat","attr":"arousal","min":75}`); `flag` gates on a character db flag
(`{"type":"flag","flag":"branded"}` or `...,"value":"pet"}`); `time` gates night/season
passages (`{"type":"time","period":"midnight"}` / `"season":"winter"`). All fail open on
error/misconfig. Denial line: per-solution `gate_denial`, else the `maze_gate_denials` pool.

---

## B. Proposed — extend the stat catalogue  [ROADMAP]
Same shape (`{"type", "min"}`), more body-state reads (all already real flags):

| type | reads | note |
|---|---|---|
| `suggestibility` | `db.suggestibility` | how programmable |
| `arousal` | arousal script value | heat-gated reveals |
| `arousal_floor` | `db.arousal_floor` | kept-edged threshold |
| `drug_dependence` | `db.drug_dependence` | dosed-enough |
| `compliance` | `db.compliance_streak` / threshold | obedient-enough |
| `brood` | sum of `offspring_counts` | has produced N get |
| `processing_tier` | `db.processing_tier` | graded to tier N |

Plus **flag gates** (boolean, no min): `bethany_owned`, `seraphine_owned`, `bethany_branded`,
`sissified`, `neutered`, `nugget`, `latex_sealed`, `pregnant`, `consent_locked`, … — "opens only
if this flag is set." (And a `not_` variant: opens only if it's *not* set.)

---

## C. Proposed — non-stat conditions for the Reveal/Gate primitive  [ROADMAP]
These make sense on **details / handles / studies / exits / mechanics**, not just maze stats:

| type | satisfied when | example |
|---|---|---|
| `studied:<zone>` | the looker has `study`'d that zone before | wall-words appear after you study the wall |
| `handled:<detail>` | they've handled a related detail | a drawer opens after you handle the latch |
| `revealed:<key>` | another reveal/trigger has fired | chained discovery |
| `holds:<tag>` | they carry an item with that tag | a lock that needs the key item |
| `action:sit` | they sat on the zone's seat | the jacuzzi dildos surface on `sit` |
| `action:enter` | they entered the zone interior | reveals inside a WombRoom |
| `relationship:<role>` | viewer's relationship to the holder (owner/peer/stranger) | handle text/availability differs for an owner |
| `time:<period>` | current period matches | a passage only open at night |
| `weather:<kind>` | current weather matches | a path only in the storm |

**State- & viewer-aware descs (#2)** reuse this same idea as a *render* selector rather than a
hard gate: pick `viewer_descs[cond]` / `state_descs[cond]` by the first matching condition, with
priority **viewer-state → room-state → time → summary → desc**.

---

## D. Data shapes (proposed)  [ROADMAP]
Keep it one tiny dict, reused everywhere:
```python
gate = {"type": "conditioning", "min": 60}          # stat gate
gate = {"type": "bethany_branded"}                  # flag gate
gate = {"type": "not_pregnant"}                     # negated flag
gate = {"type": "studied", "zone": "the_wall"}      # prereq
gate = {"type": "action", "action": "sit"}          # action reveal
```
On a detail/handle/exit: `entry["reveal"] = gate`. One checker (`gate_ok(viewer, gate, holder)`)
serves maze solutions, details, handles, studies, mechanics, and exits alike — **fails open.**

---

## E. Authoring guidance
- Gate on stats that **move in play** (conditioning/devotion/standing/suggestibility accrue;
  quota and flags are clean binaries).
- Prefer reveals that reward **attention** (`studied:`/`handled:`) or **progression** (stat/flag)
  — they make the world feel deeper, not just locked.
- Always confirm the §0 floor frees a player regardless of any gate (fails open + `escape`).
- Keep denial lines in-voice; let a hidden thing stay *hidden* (don't hint gated details in the
  base desc, or you spoil the reveal — `survey` already respects this).
