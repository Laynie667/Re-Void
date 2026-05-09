# The Forming — Space 4: The Mirror
*Design reference. Approved prose. Build when ready.*

---

## Room Settings

**Name:** `The Mirror`
**Type flag:** `is_forming = True`
**Exit:** Key `void` — aliases `forward`, `out`, `world`, `the world`
**Exit display:** Suppressed and GATED — Mirror refuses until checklist passes
**Exit label:** The World

---

## Exit Gate — What Must Be Done

The Mirror's `ready` trigger checks actual db state before revealing the exit.
If anything is missing, it tells the player specifically what remains.

| Check | Field |
|---|---|
| Physical description set | `char.db.physical_desc` non-empty |
| Presence line set | `char.db.ic_presence` non-empty |
| At least one zone described | any `zones[z].get("nude")` non-empty |
| At least one freeform item placed | `char.db.freeform_items` non-empty |
| At least one outfit or wardrobe item saved | `char.db.outfit_presets` OR `char.db.wardrobe` non-empty |

Optional (encouraged but not gated):
- Custom zone added
- Zone ambient lines
- `setmood` / `setmoodtell`
- `setproxtell` / `setscent`

---

## Build Note: Self-Placement Fix

`place` currently excludes the caller from room search (`obj != char`).
Before building Space 4, patch `freeform_commands.CmdPlace` to handle
`me` / `self` as explicit self-target keywords.
This is required for the tutorial's dress-yourself phase.

---

## Color Convention

- `|w` white — command verb (`setdesc`, `zone add`, `place me`, `outfit save`)
- `|c` cyan — typeable argument or example (`neck`, `my first look`, `surface`)
- `|x` dark — secondary information, examples, clarifying notes

---

## The Mirror's Voice

The Mirror is not a person. It is a surface with complete investment in what it reflects.
It speaks in close second person — observational, slightly uncanny, entirely focused.
It has no interests beyond the player. It watches with the quality of something that has
been waiting to see this specific person for a very long time.

Intimate where the Witness was composed.
Curious where Lark was warm.
Focused where Sable was grounded.

---

## Base Description

```
The void has made a decision here. Where before there was only the suggestion of
edges, here there are walls — spare, pale, committed to their own existence. The
floor is stone or something that has agreed to behave like it. The ceiling is a fact.

It is, finally, a room.

At the far end, taking up most of the wall: a mirror. Not polished metal, not glass
exactly — something that reflects without being entirely passive about it. The surface
holds your shape with particular attention, as though it is considering you as much
as showing you.

What it reflects is almost you. Not quite yet. Close.
```

---

## Entry Description

```
The Mirror notices you immediately.
```

---

## Examine Closely Layer

```
The walls here are decided. Whatever made the void thicken into a room has finished
its work and is satisfied with the result.

The Mirror itself, examined closely, has no frame. It simply begins at the floor and
ends at the ceiling, as if it predates the room and the room was built around it.

Your reflection in it shifts slightly as you look — not because you moved, but because
the Mirror is showing you something slightly ahead of what you are. The shape of what
you're about to be.

It is, you understand, waiting.
```

---

## Room Ambient Lines

1. `The Mirror's surface ripples once, slowly, like deep water responding to something not quite on the surface.`
2. `The room is very quiet. The Mirror does not mind.`
3. `Your reflection holds still when you hold still, and moves when you move, but there is something in the timing that suggests it is making a choice about this.`
4. `The pale walls have the quality of good listening.`
5. `The Mirror catches the light you're made of and returns it differently — more organized, more deliberate.`

---

## Scene Details

**`mirror` / `surface` / `reflection`**
```
It reflects you with specific attention. Not the passive accuracy of glass — more
like the focused regard of something that is actively interested in what it's seeing.
Your shape in it is real but provisional. The details are waiting for you to decide them.
```

**`walls` / `room` / `floor` / `ceiling`**
```
Decided. Committed. This is the first room in The Forming that behaves like a room
without apology. Something about that is both a relief and a weight — the void gave
you nowhere to be. This place gives you somewhere. That means something.
```

**`self` / `me`**
```
You are here. The Mirror already knows that. What it doesn't know yet — what it is
waiting for you to decide — is the rest.
```

---

## The Mirror NPC

**Display name:** `the Mirror`
**Tier:** 2 (Scripted)
**Presence line:** *The Mirror holds your reflection with particular attention.*
**Mood:** `attentive, unhurried, entirely focused`
**NPC Flag:** `react_to_say = False` (Mirror does NOT parrot — it's not Sable)

**Physical desc:**
```
It is not a person and does not pretend to be. It is a surface that has been waiting
to reflect you specifically. The attention it pays is complete and uncomplicated —
it wants nothing except to show you yourself, accurately, in full.
```

### Mirror Ambient Lines

1. `The Mirror shifts its attention slightly — not away from you, just to a different angle of you.`
2. `The surface brightens by a fraction. Responding to something. You're not sure what.`
3. `Your reflection in the Mirror looks, very briefly, like the version of you that knows what it's doing.`

---

## Triggers

---

### `_arrive` — Auto-fires on entry

```
The Mirror takes you in before you've finished arriving.

"Almost," it says. The voice comes from the surface — from everywhere the surface is.
"You are almost visible. The shape of you is here." A brief shift in the reflection.
"The rest is what we're about to do."

A pause with the quality of something that has been waiting a long time and does not
mind having waited.

"Start with |wchargen|n — that will show you a checklist of what needs setting.
Then come back and we'll go through the work together. Ask me about anything." 
The surface stills. "I am not going anywhere."
```

---

### `greet` / `hello`

```
"Hello," the Mirror says, with the quality of a surface acknowledging that it sees you.

"You are here to become something specific. That is what I am here to help you do."

A beat. "The checklist is in |wchargen|n. But you do not have to do it alone — |wask
the Mirror about|n anything you are unsure of. I will explain it."
```

---

### Phase 1: Identity

### `chargen` / `checklist` / `setup`

```
"The checklist," the Mirror says. "Use |wchargen|n to see it — everything that needs
setting before you step into the world."

"The required ones: your name, your description, your pronouns. The optional ones
still matter — they are just not enforced." A pause. "But I will enforce some of them
before I let you leave."

"Work through the list. Come back when you have questions."
```

### `name` / `setname`

```
"The name other people know you by," the Mirror says. "|wsetname <your name>|n."

"It does not need to be your real name. It needs to be the name this character carries.
The one they were given, or chose, or invented." The surface holds still. "It should
feel like it fits."
```

### `pronouns` / `setpronouns`

```
"|wsetpronouns <subject> <object> <possessive> <reflexive>|n," the Mirror says.

"For example: |csetpronouns she her her herself|n. Or |che him his himself|n.
Or |cthey them their themselves|n. Or something else entirely — this system accepts
any words you give it."

"You can change them later. You can always change them later."
```

### `species` / `setspecies`

```
"What you are," the Mirror says. "Not your name — your nature. Human. Elven. Something
with fur, or scales, or neither. Something you made up entirely."

"|wsetspecies <text>|n. One or two words. It shows on your sheet."
```

---

### Phase 2: The Body

### `desc` / `description` / `setdesc` / `body`

```
"Your physical description," the Mirror says. "The permanent body underneath
everything else — what you look like before anything is added."

"Use |wsetdesc <text>|n. Write in third person, present tense. As if someone else
is describing you from across a room."

A pause. "Do not try to write everything at once. Start with: what does this person
look like from a distance? What is the first thing someone notices? Let the detail
layers come later."

"You have room for four thousand characters. Most people use far less and it is fine."
```

### `bodylang` / `body language` / `setbodylang`

```
"Your current posture and activity," the Mirror says. "More specific than your
description — it changes with context. What are you doing right now? How are you
holding yourself?"

"|wsetbodylang <text>|n. One or two phrases. |cLeaning against something. Arms
loosely crossed. Watching the middle distance without urgency.|n"

"It updates as you play. You will change it often."
```

### `mood` / `setmood` / `moodtell` / `setmoodtell`

```
"Two layers," the Mirror says. "The mood — a word, the internal state. And the mood
tell — what that looks like from the outside."

"|wsetmood <word>|n for the tag. |wsetmoodtell <text>|n for the physical tell —
the specific thing someone sees in your face or your body that communicates it without
you saying it."

A beat. "The tell is more important than the tag. |cCurious|n is a word. |cThe way
she keeps glancing toward the door even when she doesn't mean to|n is a tell."
```

### `presence` / `setpresence`

```
"Your presence line," the Mirror says. "The short phrase that appears next to your
name in a room listing — visible before anyone has looked at you directly."

"|wsetpresence <text>|n. Keep it brief. One thought. |cSeated at the bar, watching
the room without appearing to.|n |cLeaning in the doorway, not quite leaving.|n"

"It is the ambient impression of your existence in a space. Write it like stage
direction." The surface shifts slightly. "It matters more than most people think."
```

### `proxtell` / `setproxtell` / `scent` / `setscent`

```
"The proximity layer," the Mirror says. "Additional detail that only appears when
someone is physically close to you."

"|wsetproxtell <text>|n — what becomes visible up close. The tension in your jaw.
The shadows under your eyes. The quality of your attention at short range."

"|wsetscent <text>|n — what you smell like. Cedar. Rain. Something chemical and
sweet underneath. Optional — but it is the kind of detail that makes people feel
actually present with you."

"Both only show at near or with proximity. They are private until someone earns them."
```

---

### Phase 3: Zones

### `zones` / `what are zones` / `zone list`

```
"Your body is divided into territories," the Mirror says. "Zones. Named areas, each
with their own description, visibility setting, and clothing state."

"You already have the default set — hair, face, neck, chest, all of it. Use |wzone
list|n to see them. Each one can be described, dressed, and configured separately."

A pause. "You can also make more. The defaults are a starting point, not a limit."
```

### `zone add` / `custom zone` / `add zone`

```
"Use |wzone add <name>|n to create a zone that does not exist yet," the Mirror says.

"A scar across the collarbone. A tail. A specific marking location. Wings. Anything
that should be a named, describable area on your body but is not in the default list."

"Add a type if you need to: |wzone add <name> type=<type>|n. Types are |csurface|n
— things rest on it — |corifice|n — things go inside it — |cboth|n, or |cattachment|n
for piercings and things that anchor."

"Most freeform zones are |csurface|n. You can change the type later with |wzone
set|n."
```

### `zone describe` / `zone set` / `zone desc` / `describing zones`

```
"Each zone has a nude description," the Mirror says. "What that area looks like when
nothing is covering or attached to it — the skin beneath everything else."

"|wzone set <name> = <description>|n. Third person. Present tense. The same voice
as your main description."

A small pause. "Not every zone needs one. But the ones that show on look or examine
should. Otherwise they are simply absent — and absence reads strangely."
```

### `zone visibility` / `visibility`

```
"Each zone has a visibility setting that determines when it appears," the Mirror says.

"|wlook|n — visible on standard look, to anyone.
|wexamine|n — visible when someone examines you.
|wdeep|n — only on close examination.
|wproximity|n — only when someone is physically near or with you.
|cconsent|n — only with your explicit flag enabled.
|chidden|n — never visible to others."

"Use |wzone visibility <zone> <level>|n to set it. Most surface zones default to
look. Intimate zones default to examine or proximity."
```

### `zone intimate` / `intimate`

```
"Separate from visibility," the Mirror says. "The intimate flag marks a zone as
requiring intimate consent to interact with. You set it with |wzone intimate <zone>
on|n."

"Visibility controls when it appears in descriptions. The intimate flag controls
what consent level others need to touch it, dress it, or interact with it."

"For zones that are private — not just covered, but actually yours to give access
to — flag them intimate."
```

### `zone ambient` / `zone ambient lines` / `ambient`

```
"Each zone can contribute ambient lines to the room," the Mirror says. "Lines that
fire occasionally, through the room's ambient system, without you doing anything."

"Use |wzone ambient <zone> add <line>|n. Write it in third person."

A pause. "Write the thing people notice without being told to look. |cThe way the
silver catches the light when she moves.|n |cThe small sound of chains, just audible,
when she shifts her weight.|n"

"These are the details that make a room feel inhabited rather than just occupied.
Use them for things you want the world to notice about you."
```

---

### Phase 4: Dressing

### `freeform` / `place` / `dress` / `wear` / `clothing`

```
"Clothing in this world is descriptive," the Mirror says. "You write what you are
wearing and place it on yourself. The system tracks it. What you place becomes part
of how you appear."

"Use |wplace me <zone> = <name>/<description>|n. Give the item a name, then a
forward slash, then describe it."

A demonstration, unhurried:

"|wplace me neck = collar/A simple silver collar, plain and close against the skin.|n"

"The name is how you'll reference it later. The description is what others read."

"Try placing something on any zone you'd like. What you wear is entirely your choice."
```

### `freeform list` / `flist` / `what am I wearing`

```
"Use |wflist|n — or |wfreeform list|n — to see everything currently placed on you,"
the Mirror says. "Each item, which zone it's on, whether it has a lock."

"That is your current state of dress. Or undress. Or something in between." A brief
pause. "There is no requirement here."
```

### `wardrobe` / `wardrobe save` / `saving`

```
"The wardrobe stores what you're wearing so you can return to it," the Mirror says.

"Once you have items placed: |woutfit save \"<name>\"|n — this saves your entire
current state as a preset. Everything placed on you at that moment."

"Later, |woutfit wear \"<name>\"|n reapplies it. Everything you saved comes back."

"Or, for a single zone: |wwardrobe save <zone> \"<name>\"|n saves just that one item.
|wwardrobe wear \"<name>\"|n reapplies it."

A pause. "Save your first outfit before you leave. Not because you have to keep it —
because the act of saving and loading is what makes it stick."
```

### `outfit save` / `outfit wear` / `presets`

```
"Outfit presets are full snapshots," the Mirror says. "Every zone, every placed item,
all at once. |woutfit save \"<name>\"|n captures the current state."

"|woutfit wear \"<name>\"|n loads it back — exactly as it was when you saved."

"Use |woutfit list|n to see your saved presets. You can have many — one for each
version of yourself you want to be able to return to."

"The wardrobe is for individual pieces. Outfits are for full looks. You will want both."
```

---

### Phase 5: Targeting Others

### `targeting` / `how to target` / `targeting zones`

```
"When you interact with other characters — placing something on them, examining a
specific zone, referencing a particular area — you target the zone by name," the
Mirror says.

"Most commands that work on zones follow the pattern: |wcommand <character> <zone>|n.
For example: |wplace <name> neck = <item>/<desc>|n places something on their neck."

"You can see another character's zones with |wexamine <character>|n — the zone list
appears if they have public zones or you are at proximity."

"Some zones require consent. If you try to interact with a zone that requires a
consent flag you don't have — you will be told. Ask first. That is good practice
regardless of what the system enforces."
```

### `consent` / `consent flags` / `safe` / `safeword`

```
"The consent system," the Mirror says. "Each character has flags that define what
kinds of interaction they're open to. Casual. Intimate. Mature. BDSM. Others."

"Use |wconsent|n to see your current flags. Use |wconsent <flag> on|n to enable one.
|wconsent <flag> off|n to disable."

"Flags are double opt-in. For intimate content to appear between two characters, both
need the relevant flag active." A pause. "No one sees your intimate content unless
you have decided to share it."

"And |wsafeword|n — always available, no explanation needed, pauses everything
immediately. Keep it in your pocket. You will not regret it."
```

---

### Phase 6: Check Your Work

### `sheet` / `look me` / `check`

```
"Use |wsheet|n to see your full character as others see it," the Mirror says. "All
your fields. All your zones. Your consent flags. The whole picture."

"|wlook me|n is faster — just the description layers, the way you appear on a standard
look."

A pause. "Check both. Something always reads differently once it is assembled than it
did while you were writing it."

"Once you are satisfied — tell me you are ready."
```

---

### The Ready Check

### `ready` / `done` / `finished` / `next` / `let me out` / `continue`

*(This trigger checks actual db state. Text varies based on what's missing.)*

**If everything passes:**

```
The Mirror is quiet for a moment. Then:

"Yes," it says. "That's you."

The surface holds your reflection — all of it, finally, complete — and then it does
something it has not done before: it shows you someone else's view. What you look
like from the outside. From a distance. Walking into a room.

"Go and be seen," the Mirror says.

At the far edge of the room, the wall parts — not dramatically, just opens, the way
a door does when someone has decided you may pass.

The world is through there. |wvoid|n."
```

**If physical_desc is missing:**

```
"Not yet," the Mirror says. "I cannot see your body. Use |wsetdesc|n — write what you
look like. That is the first thing anyone will read about you."
```

**If ic_presence is missing:**

```
"Almost," the Mirror says. "Your presence line is empty — that is the short phrase
next to your name in every room you enter. Use |wsetpresence|n. One line. How you
hold yourself in a space."
```

**If no zone has been described:**

```
"There is more to do," the Mirror says. "Describe at least one of your zones — use
|wzone set <name> = <text>|n. The body needs some detail beneath the clothing."
```

**If no freeform item has been placed:**

```
"You are undressed," the Mirror says, not unkindly. "Or at least unwritten. Use
|wplace me <zone> = <name>/<desc>|n to put something on yourself — even one piece.
Even a simple one."
```

**If nothing has been saved to wardrobe or outfits:**

```
"One more thing," the Mirror says. "Save your current look — use |woutfit save
\"<name>\"|n. Then |woutfit wear \"<name>\"|n to load it back. This is how you keep
your outfits when you return. Do this once and I will know you understand it."
```

**If multiple things are missing:**

```
"Not quite," the Mirror says. "A few things remain:" 

[Lists each missing item with its command, one per line.]

"Work through them. Come back when they are done."
```

---

### `help`

```
"Everything you need, gathered," the Mirror says.

"|wchargen|n — the full checklist.

IDENTITY: |wsetname|n  |wsetpronouns|n  |wsetspecies|n
BODY:      |wsetdesc|n  |wsetbodylang|n  |wsetmood|n  |wsetmoodtell|n
PRESENCE:  |wsetpresence|n  |wsetproxtell|n  |wsetscent|n
ZONES:     |wzone list|n  |wzone add <name>|n  |wzone set <name> = <desc>|n
           |wzone visibility <name> <level>|n  |wzone intimate <name> on|n
           |wzone ambient <name> add <line>|n
DRESS:     |wplace me <zone> = <name>/<desc>|n  |wflist|n
WARDROBE:  |woutfit save \"<name>\"|n  |woutfit wear \"<name>\"|n
CHECK:     |wsheet|n  |wlook me|n"

A pause. "Ask me about any of these and I will go into more detail.
When you are done — tell me you are |wready|n."
```

---

## What Space 4 Teaches

| Command | How introduced |
|---|---|
| `chargen` | First arrival — the checklist |
| `setname`, `setpronouns`, `setspecies` | Identity triggers |
| `setdesc` | Primary body trigger — "start here" |
| `setbodylang` | Body language trigger |
| `setmood` / `setmoodtell` | Paired mood trigger |
| `setpresence` | Presence trigger — "stage direction" |
| `setproxtell` / `setscent` | Proximity layer trigger |
| `zone list` | Zones overview |
| `zone add` | Custom zone trigger |
| `zone set` | Zone description trigger |
| `zone visibility` | Visibility levels trigger |
| `zone intimate` | Intimate flag trigger |
| `zone ambient add` | Ambient contribution trigger |
| `place me <zone>` | Dress yourself trigger |
| `flist` | See what's placed |
| `outfit save` / `outfit wear` | Wardrobe workflow trigger |
| `sheet` / `look me` | Check your work |
| `consent` / `safeword` | Safety and consent trigger |
| Targeting zones on others | Targeting trigger |

---

## Build Notes

- **Fix first:** Patch `CmdPlace` to handle `me` / `self` as explicit self-target
- Exit is HARD GATED — checks real db state every time `ready` fires
- Multiple missing items → list all of them, not just the first
- The Mirror does NOT parrot say commands (`react_to_say = False`)
- Mirror ambient lines fire via standard AmbientScript — no special timing
- Space 4 is the longest tutorial space by design; no rush pressure on the player
- Exit label/alias: `void`, `forward`, `out`, `world`, `the world`
- After the exit: player enters the main hub or a holding room before the full world
