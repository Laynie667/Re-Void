# The Forming — Space 5: The Fitting
*Design reference. Approved prose. Build when ready.*

---

## Room Settings

**Name:** `The Fitting`
**Shop name (display/lore):** `Wren & Co.`
**Type flag:** `is_forming = True`
**Exit:** Key `void` — aliases `out`, `world`, `forward`, `the door`
**Exit display:** Suppressed and GATED — Wren refuses until checklist passes
**Exit label:** The World
**Post-exit note:** The door ceases to exist once the player passes through. The Forming is done.

---

## Color Convention

- `|w` white — command verb (`emote`, `place`, `permit`, `examine`, `social`)
- `|c` cyan — typeable argument or example (`companion`, `bow`, `neck`)
- `|x` dark — secondary information, catalog-voice detail

---

## Exit Gate — What Must Be Done

| Check | Field |
|---|---|
| At least one item placed on the companion | `companion.db.freeform_items` non-empty (items placed by this player) |
| At least one social emote used | tracked via `caller.db.forming_used_social = True` |

Optional (encouraged but not gated):
- `permit` command used or attempted
- Intimate zone access attempted (triggers consent explanation naturally)
- `examine companion` at proximity

---

## Wren's Voice

Wren is the shopkeeper. She has been doing this for a long time and she is not moved by anything.
She is not unkind. She is efficient. These are different things and she is aware of the distinction.

She speaks in clipped, complete sentences. She does not over-explain. She does not under-explain.
She explains exactly once and then expects you to have retained it.

Her affect is that of someone who has organized the intimate zones of a thousand demonstration models
and finds the work no more remarkable than shelving books. The shop is her domain.
She is the most competent person in it.

She is blunt with the specific quality of someone who could be cruel but has decided not to bother,
because cruelty takes more energy than she is willing to spend on you.

**She can be used again.** Wren — or her twin — operates a shop in another realm.
Players who encounter her there will recognize her immediately.

---

## Base Description

```
The void deposits you somewhere that has made significant decisions about what it
wants to be.

The shop is narrow and precise — shelves running floor to ceiling on both sides, each
one organized with the specificity of someone who cares deeply about category. Glass
cases along the left wall display items arranged by size, function, and a third
criterion you cannot immediately determine. The lighting is warm, even, and has no
interest in flattering anyone.

At the back, behind a counter that has survived more than you have, a woman is writing
something down. She does not look up when you arrive.

To the right, on a low raised platform, a figure stands very still.
```

---

## Entry Description

```
Wren does not look up.

"Close the door," she says. There is no door to close. She says it anyway.
```

---

## Examine Closely Layer

```
The shelves are better organized than anything you have encountered in The Forming.
Labels in small, precise handwriting. Items arranged with the logic of someone who
has a system and has never been persuaded to explain it.

The glass cases on the left contain things that are technically describable and yet
resist summary. All of them are labeled. All the labels are extremely specific.

Wren is still writing. Whatever it is, she is going to finish it.
```

---

## Room Ambient Lines

1. `Something in the left case catches the light and holds it with unnecessary enthusiasm.`
2. `Wren turns a page. She reads it. She makes a small sound of professional dissatisfaction.`
3. `The companion on the platform shifts its weight by a fraction — or perhaps you only imagined this.`
4. `The shop is very organized. You feel faintly judged by the organization.`
5. `Wren looks up briefly, makes an assessment, returns to her work.`

---

## Scene Details

**`shelves` / `items` / `products`**
```
Organized by a system you do not fully grasp but which clearly makes sense to someone.
The labels are clinical. The items are not. You get the sense that Wren would describe
all of them with the same energy she uses to describe everything else: accurately,
completely, and without ceremony.
```

**`case` / `cases` / `glass case`**
```
The left wall's display cases contain items arranged by size, function, and a third
category whose label you can read but whose organizing logic remains opaque. All of
it is priced. Wren has opinions about what things are worth.
```

**`counter` / `desk`**
```
Old, solid, covered in paperwork that is also organized. Wren's workspace. The pen
she is using has clearly been used for a very long time. She has not replaced it.
```

**`wren`**
```
Sharp-featured, somewhere between thirty and the concept of having stopped counting,
with the particular posture of someone who has arranged their skeleton for maximum
efficiency over many years. Her hair is pulled back with the single-minded practicality
of someone who solved that problem once and has not revisited it. She looks like
someone who has been asked the same question by many different people and has answered
it every time.
```

**`companion` / `model` / `figure` / `doll` / `platform`**
```
The demonstration model stands on the low platform to the right — present, attentive,
dressed in something that implies the possibility of being undressed. Its zones are
visible at varying degrees of examination. It is, as far as you can tell, the most
complete character description you have encountered so far in this place.

It is also clearly a product.
```

---

## Wren NPC

**Display name:** `Wren`
**Tier:** 2 (Scripted)
**Presence line:** *Wren is behind the counter, writing something down.*
**Mood:** `efficient, unsentimental, slightly impatient`
**react_to_say:** `False`

**Physical desc:**
```
Sharp-featured and economical in all things. She has the posture of someone who has
made specific decisions about how she is going to hold herself and has not reconsidered
them. Her attention, when she gives it, is complete — and clearly borrowed, to be
returned promptly when she is done with you.
```

### Wren Ambient Lines

1. `Wren makes a note on whatever she is writing. The note is short.`
2. `She glances at the companion on the platform with the expression of someone checking that something is still where they left it.`
3. `Wren sets her pen down, picks it up again. Continues.`
4. `She looks at you. Then back at her paperwork. You have been assessed.`

---

## The Companion (Display Model)

**Display name:** `the companion`
**Object type:** Scripted interactive prop (not a full NPC — no triggers, no ambient)
**Platform:** Low raised dais, right side of shop

The companion exists to demonstrate a fully built character from the outside. It has:
- A complete physical description
- Zones at every visibility level, including intimate-flagged zones
- Freeform items already placed across multiple zones
- An outfit preset saved (demonstrable via `flist companion`)

Players interact with it to learn: zone targeting, examine depth, permit/consent system,
and how to `place` items on something other than themselves.

### Companion Physical Description

```
The demonstration model is built to show range. Proportions that read as intentional
rather than accidental — everything placed with the awareness of being looked at.
The kind of figure that makes the concept of clothing feel like a considered choice
rather than a default.

Its expression is attentive. Patient, in the way of things that do not experience the
passage of time as loss.
```

### Companion Presence Line

```
The companion stands very still on the platform, dressed in something that implies more than it covers.
```

### Companion Zone Layout

The companion's zones demonstrate the full visibility spectrum and intimate flag system.

| Zone | Visibility | Intimate | Description (abbreviated) |
|---|---|---|---|
| `hair` | look | no | Dark, swept back, held with something minimal |
| `face` | look | no | Even features, particular quality of attention |
| `neck` | look | no | Clean line, unadorned except what's been placed |
| `hands` | look | no | Still. The kind of still that reads as practice |
| `chest` | examine | no | Where the garment begins its commitments |
| `waist` | examine | no | The line where the garment makes its first decision |
| `arms` | examine | no | Fine detail work on the inner wrist, not immediately visible |
| `back` | examine | no | Bare from shoulder to mid-back where the garment begins |
| `hips` | proximity | no | Specific. Intentional. Close examination required |
| `thighs` | proximity | no | The garment suggests them more than it conceals |
| `lower_back` | proximity | no | A small mark here, visible only at close range |
| `chest_intimate` | proximity | yes | Present. Detailed. Requires permit. |
| `hips_intimate` | consent | yes | Fully described. Consent-gated. Requires explicit flag. |

### Companion Freeform Items (Pre-placed)

These are already on the companion when the player arrives, demonstrating freeform dressing:

- `neck` — **collar**: *A slim band of dark leather, plain, buckled close against the skin. A single ring at the front.*
- `waist` — **corset**: *Black, structured, laced at the back with enough tension to be intentional. It holds the torso with opinion.*
- `wrist` — **cuff**: *Matching leather, left wrist only. Attached. The ring on it echoes the one at the throat.*

---

## Triggers

### `_arrive` — Auto-fires on entry

```
Wren finishes her sentence before she looks up. This takes approximately four seconds.

"New one," she says, not as a greeting, more as a classification. She sets her pen
down with the care of someone who will be picking it up again shortly.

"Wren. This is my shop." She does not elaborate on what the shop is or what it sells.
You can see what it sells.

"The model on the platform is a demonstration unit. You are going to interact with
it." She says this the way someone says something that is going to happen regardless
of your feelings about it.

"Examine it. Place something on it. Learn the permit system when you run into it."
She picks up her pen. "Then I will let you leave."
```

---

### `greet` / `hello`

```
"We have met," Wren says. "I told you my name and what you were going to do. Are
you doing it?"

A pause.

"The companion is to your right. |wexamine |ccompanion|n — that is the starting
point. Then |wplace |ccompanion |c<zone>|n|w = |c<name>/<description>|n when you
are ready to actually do something."
```

---

### `companion` / `what is the companion` / `doll` / `model`

```
"Demonstration unit," Wren says. "Fully described. Multiple zones at different
visibility depths. Several of them flagged intimate." She says intimate with the same
energy she uses for all other words.

"It exists so you can see what a complete character looks like from the outside —
and so you can practice interacting with one without bothering someone real."

A brief pause.

"Examine it at different depths. Get close to it. Try to interact with something
that requires a permit." She looks at you steadily. "That last one is especially
instructive."
```

---

### `examine` / `look at`

```
"Right," Wren says. "The examine command pulls more detail than look. |wexamine
|ccompanion|n — standard examine. |wexamine |ccompanion|n |wat |cproximity|n, or
just |wapproach |ccompanion|n first — proximity unlocks a different layer."

"You can also target zones directly. |wlook at |ccompanion chest|n. |wexamine
|ccompanion neck|n." She sets her pen down again, fully this time.

"The companion's zones are set at every visibility level on purpose. Look at it
until you've seen the difference between them."
```

---

### `approach` / `proximity` / `beside`

```
"Physical position affects what you can see," Wren says. "And what you can do.
|wapproach |ccompanion|n moves you to near. |wbeside |ccompanion|n moves you to
with." 

"Proximity unlocks description layers. On the companion — several zones only appear
when you're close. Try it."

A beat. "It works the same way with real people. Proximity is social before it is
mechanical. Ask before you close distance with someone who hasn't invited it."
```

---

### `emote` / `social` / `socials` / `social emotes`

```
"The social emote library," Wren says. "Type |wsocials|n to see the full list.
Most of them work without a target — they address the room. Most also accept a target."

She demonstrates without ceremony: she nods at you. One small, precise downward
motion of her head.

"That was |wnod|n. It can also be |wnod |ccompanion|n, or |wnod |c<player name>|n.
The library is large. |wsmile|n. |wbow|n. |wtouch|n. |wlean|n. Most things you
might want to do."

"Some of them require a permit flag from the target. Those are noted in the list."
```

---

### `permit` / `what is permit` / `permission`

```
"The permit system," Wren says. "Some social emotes require the target to have
permitted that category of contact. |wsmile|n — open. |wtouch|n — requires casual
permit from the target."

"Use |wpermit <player> <category>|n to grant permission. |wpermit <player> off|n
to revoke it. The companion has its permit flags pre-set for demonstration — you
will run into them when you try something that requires one."

A brief pause. "The system does not stop you from asking. It stops you from doing
without asking. That distinction is the point."
```

---

### `place` / `placing` / `how to place`

```
"Same as placing on yourself," Wren says, "but with a target. |wplace |ccompanion
|c<zone>|n|w = |c<name>/<description>|n."

She glances at the companion.

"For example: |wplace |ccompanion |cneck|n|w = |cchoker/A thin cord of dark ribbon,
tied close.|n" A pause. "Name. Slash. Description. The zone must exist on the target.
If you do not know the zone names, |wexamine |ccompanion|n lists them."

"Put something on it. It does not have to be interesting. It has to be done."
```

---

### `flist` / `freeform list` / `what is on it`

```
"|wflist |ccompanion|n," Wren says. "Shows everything currently placed on the
demonstration unit. You can see what it arrived with and what you have added."

"On a real character, |wflist|n without a target shows your own current state of
dress. Both are useful. Check them."
```

---

### `pose` / `emote`

```
"Third person action," Wren says. "|wpose <text>|n — or |wemote|n, same thing.
Writes the action with your name at the front."

"Use it in context. Right now, in this room, it reads to anyone present. The
companion on the platform. Me." She does not look particularly invested in being
included in your emotes.

"Write what your character is doing. Not what you want them to do — what they are
doing, present tense, third person." A beat. "You are the author. The character is
what you write."
```

---

### `consent` / `flags` / `safety`

```
"Consent flags determine what others can do with your character," Wren says. "You
set them. You control them. Other players cannot override them."

"|wconsent|n — view your current flags. |wconsent <flag> on|n — enable one.
The flags are: casual, intimate, mature, bdsm, lead_follow, restraint, plock."

She looks at you. "The companion has some of its flags set. You will find this out
when you try to interact with a zone that requires one. That is the point of the
exercise."

"And |wsafeword|n — always in your pocket, no explanation required. You already
know this from Sable."
```

---

### `help`

```
"Short version," Wren says.

"|wexamine |ccompanion|n — see zone depth and visibility.
|wapproach|n / |wbeside |ccompanion|n — proximity unlocks more.
|wplace |ccompanion |c<zone>|n|w = |c<name>/<desc>|n — put something on it.
|wflist |ccompanion|n — see what's on it.
|wsocials|n — full emote list.
|wpermit|n — consent for social contact.
|wpose <text>|n — third person action.
|wconsent|n — your flags."

She picks up her pen.

"When you have placed something on the companion and used at least one social emote:
tell me you are |wready|n."
```

---

### The Ready Check

### `ready` / `done` / `finished` / `let me out` / `next`

**If freeform item not placed on companion:**

```
"You have not placed anything on the companion," Wren says. "Do that first.
|wplace |ccompanion |c<zone>|n|w = |c<name>/<desc>|n."
```

**If no social emote used:**

```
"You have not used a social emote," Wren says. "Type |wsocials|n, pick one,
use it. That is the entire requirement."
```

**If both are missing:**

```
"Two things," Wren says. "Place something on the companion. Use a social emote.
Then come back."
```

**If everything passes:**

```
Wren sets her pen down.

"Good." She does not elaborate on what was good. She looks at you with the
expression of someone who has made a decision about you and found it acceptable.

She comes out from behind the counter.

"The world is through there." She gestures toward a section of wall that has,
until this moment, not been a door. It is, now, briefly, a door.

She moves toward you with the specific purpose of someone who intends to relocate
a problem that has been solved.

You are, before you fully understand what is happening, through it.

The door, you understand from the other side, is no longer there. The Forming is
finished. What you are now is what you arrived as.

Wren, presumably, goes back to her paperwork.
```

---

## What Space 5 Teaches

| Command | How introduced |
|---|---|
| `examine <target>` | Companion is the demonstration subject — depth varies |
| `examine <target> <zone>` | Zone targeting on something other than self |
| `approach` / `beside` | Proximity unlocks companion's deeper zones |
| `socials` | Full list — Wren demonstrates with a nod |
| Social emotes with targets | `bow companion`, `nod`, `smile <name>` |
| `permit` | Hit naturally when a companion zone requires it |
| `place <target> <zone>` | Core exercise — place something on the companion |
| `flist <target>` | Check what's been placed |
| `pose` / `emote` | Third person action, in context |
| `consent` | Flags explained through companion's pre-set state |

---

## Guide Arc Note

- **The Witness** — still, ancient. Teaches orientation.
- **Lark** — warm, floating. Teaches wisp identity.
- **Sable** — grounded, dry, embodied. Teaches what a body means.
- **The Mirror** — intimate, focused. Teaches what the character becomes.
- **Wren** — efficient, impatient, entirely competent. Teaches how to be in the world with other people.

Each one models a different answer to *what are you here for?*

---

## Build Notes

- Companion is a scripted object, not a full NPC — no ambient lines, no trigger system
- Companion's zone layout must be built with correct visibility flags for each zone
- Companion's intimate zones must have `intimate = True` and appropriate consent gates
- Companion's pre-placed freeform items (collar, corset, cuff) should be set at spawn
- Exit triggered by Wren's `ready` check, not by player typing a direction
- Exit fires a special description (the tumble), then moves player to hub
- **Door disappears** — after player passes through, the exit link is removed from this room for that player. The room itself may persist for other new arrivals.
- Wren and the shop may recur in another realm — keep her characterization consistent. She is the same person. She does not remember you specifically.
- `forming_used_social` flag set on player when any social emote fires in this room — cheapest tracking method
- Room name "The Fitting" — sign above the door (if ever seen from outside) reads `Wren & Co.`
