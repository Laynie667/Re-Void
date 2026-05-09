# The Forming — Space 3: Almost
*Design reference. Approved prose. Build when ready.*

---

## Room Settings

**Name:** `Almost`
**Type flag:** `is_forming = True`
**Exit:** Key `void` — aliases `deeper`, `inward`, `mirror`, `the mirror`, `forward`
**Exit display:** Suppressed until Sable reveals it via `ready` trigger
**Exit label (when revealed):** The Mirror

---

## Color Convention

- `|w` white — command verb (`setdesc`, `setpresence`, `say`, `pose`)
- `|c` cyan — typeable content or example text

---

## The Parrot Mechanic

When a player uses `say <text>` in this room, Sable reacts.
Implemented via `npc.db.react_to_say = True` + `on_hear_say(caller, text)` hook.
The say command calls `on_hear_say` on any NPC in the room with that flag set.

Sable has five parrot responses, chosen randomly. `{text}` = what the player said.
`{name}` = the player's display name.

**Response pool:**

```
1. '"{text}," Sable echoes back, matching your cadence with mild precision. They look
   faintly entertained. "That is the |wsay|n command. It sounds exactly like you,
   which is the point. Try |wpose|n next — that is the third person version."'

2. 'Sable tilts their head. "{text}," they repeat, with the quality of someone tasting
   a phrase. A beat. "Good. Now — same thought, |wpose|n it. Write what you are doing
   when you say it. That is how this world actually reads."'

3. '"Oh, we are saying things," Sable says, pleased. "{text}." They nod once, as if
   approving of the attempt. "|wsay|n is your voice in the room. |wpose|n is your
   body. You will need both."'

4. '"{text}," Sable repeats back, perfectly. A small, dry smile. "Yes. That worked.
   Welcome to verbal communication." They gesture, casual. "Now try |wpose|n — write
   what you are doing in third person. |cYour Name reaches for something|n."'

5. 'Sable pauses in whatever they were doing. "{text}," they echo, with the quality of
   someone who found this word choice personally interesting. "Valid. Say that again,
   but use |wpose|n and give it a body."'
```

---

## Base Description

```
The space here has more intention than the ones before it. The grey-white hasn't
resolved into anything you'd call a room, but it's trying — there are suggestions at
the edges of what walls might look like, if walls were interested in applying for the
position. The floor beneath you has more conviction than it did before.

There are fewer lights here. The drift has thinned. What remains is more deliberate.

Leaning against what might become a wall, if the wall decided to commit, is a person.
An actual person — not a light, not a figure of composed stillness, not an impression
of presence. A person with a face and hands and a particular quality of existing that
takes up space in a way you haven't encountered yet in this place.

They're looking at you like they remember something.
```

---

## Entry Description

```
The almost-room settles slightly, as if your arrival gave it something to work with.
```

---

## Examine Closely Layer

```
The walls here are applying for the position without having been hired yet. There is
a surface-ness at the edges of this space — a commitment to having edges that wasn't
present before. It hasn't quite resolved, but it's further along than nothing.

You are still light. Still wisp. But this space is making you feel the absence of a
body more specifically than before. It isn't unpleasant. It's information.
```

---

## Room Ambient Lines

1. `At the edge of your vision, something almost resolves into a wall, then changes its mind.`
2. `The air here has a different quality — heavier, somehow. More specific.`
3. `Sable watches the almost-space with the expression of someone who finds it genuinely interesting after a long time.`
4. `A sound at the edge of hearing — not music, not voice, just the suggestion of a world with content in it.`

---

## Scene Details

**`wall` / `walls` / `edges`**
```
The walls here are applying for the position without having been hired. There is a
surface-ness at the edges — a commitment to having edges. It hasn't resolved yet.
It's trying.
```

**`floor`**
```
More convincing than the one before. Whatever this place is built on, it's getting
more serious about the concept.
```

**`sable` / `person`**
```
Dark-haired, unhurried, with the quality of attention that comes from spending time
in a world where attention matters. Their face is particular — not remarkable from a
distance, very specific up close. They're wearing something simple. Their hands are
still. They look like someone who knows what they look like, which is its own kind of
confidence.
```

**`hands`**
```
Sable's hands are still. People who are comfortable in their bodies do that — keep
their hands without needing to put them somewhere purposeful. You notice this because
you don't have hands yet.

You will.
```

**`self` / `me`**
```
You are still light — still wisp — but this space is making you feel the absence of
a body more specifically. Not as a lack. More like standing outside a room and being
able to smell what's cooking inside.
```

---

## Sable NPC

**Display name:** `Sable`
**Tier:** 2 (Scripted)
**Flag:** `react_to_say = True` — enables parrot mechanic
**Presence line:** *A person — actually, unmistakably a person — leans against the almost-wall, watching with calm curiosity.*
**Mood:** `present, dry, genuinely interested`

**Physical desc:**
```
Dark-haired and moderate in most physical ways, except for the quality of their
attention, which is absolute. They carry themselves with the ease of someone who has
been in far stranger places than this one and found them interesting.
```

### Sable Ambient Lines

1. `Sable turns a small object over in one hand — something you can't quite make out — then stills.`
2. `They glance toward the almost-walls with the expression of someone checking on something that's slowly improving.`
3. `Sable exhales quietly. It is such a specific, bodily thing that it's almost startling in this place.`

---

## Triggers

### `_arrive` — Auto-fires on entry

```
The person pushes off the wall when you arrive. Not urgently — just the way people
move when they've been waiting and the thing they were waiting for has shown up.

"There you are," they say. "I'm Sable."

They let that sit for a moment — the simple fact of a name, a voice, the way they
take up space.

"You've done the wisp part, I take it. Good. This next bit is different." They look
at you steadily. "You're about to get a body. I want you to understand what that
means before you walk into the Mirror."

A pause, not unkind. "|wlook at |cSable|n, if you want. Then |wgreet |cSable|n, and
we'll get into it."
```

### `greet` / `hello`

```
"Already handled," Sable says, mildly amused. "But yes — |wgreet|n is how you open
a conversation with someone who hasn't introduced themselves yet. I have, so now you
can just |wsay|n things."

A small gesture, an invitation. "Try it. Say something. Doesn't matter what — I want
you to see how the command lands."
```

### `say` (topic trigger — player explicitly asks about say)

```
"|wsay <text>|n — your voice into the room," Sable says. "Spoken, in the moment,
out loud. Everyone present hears it."

"The partner to it is |wpose|n. Third person — it writes what your body does.
'|cYour Name reaches for something.|n' '|cYour Name goes quiet.|n'" They tilt their
head. "Say and pose. Those two are most of what you'll use."
```

### `pose` / `emote`

```
"Third person," Sable says. "You're always the author, but in the world you're also
the character. |wpose <action>|n — or |wemote|n, same thing — writes the action with
your name at the front."

"The important thing: you're writing a character who happens to be you. Or whoever
you decide to be." A beat. "That distinction matters more than it sounds like it
should."
```

### `desc` / `setdesc` / `description` / `what do I look like`

```
"Start here," Sable says. "Your physical description — the permanent body underneath
everything else. What you look like before anything else is applied."

"Use |wsetdesc <text>|n. Write it in third person, present tense — as if someone
else is looking at you. You have a lot of room. Use it."

They pause. "Don't try to write everything. Start with: what do you look like from
across the room? Let the rest come from the details."
```

### `presence` / `setpresence`

```
"Your presence line," Sable says. "The short thing other people see next to your
name in a room listing — before they've even looked at you properly. What you're
doing. How you're holding yourself. The ambient impression of your being somewhere."

"Use |wsetpresence <text>|n. Keep it short — one phrase. |cseated at the bar, not
quite watching the door|n. |cleaning against the wall, weight on one hip|n."

A small pause. "It's the first thing anyone reads about you. It's worth caring about."
```

### `bodylang` / `setbodylang` / `body language`

```
"Body language sits just beneath the presence line," Sable says. "More specific.
Your posture, your activity, your current physical state."

"|wsetbodylang <text>|n. Where your presence line is the ambient impression, body
language is the detail — what someone notices when they actually look."

They demonstrate without commenting on it: Sable shifts their weight slightly, resettles against the wall. The quality of the room adjusts around it.

"Small changes read clearly here. Use that."
```

### `mood` / `setmood` / `moodtell` / `setmoodtell`

```
"Two parts," Sable says. "The mood — just a word, the internal state. And the mood
tell — what that state looks like from the outside."

"|wsetmood <word>|n sets the tag. |wsetmoodtell <text>|n sets the physical tell —
the specific thing someone sees in your face or body that communicates it without
you saying it."

They glance at you. "The tell is more important than the tag. Anyone can say they're
melancholy. The tell is what makes it land."
```

### `proxtell` / `setproxtell` / `proximity`

```
"This one's subtle," Sable says. "Your proximity tell — additional detail that only
appears when someone is physically close to you. Not in the room, not across it.
Close."

"|wsetproxtell <text>|n. Write what becomes visible up close. The shadows under your
eyes. The way your jaw holds tension. What you smell like." They pause. "What someone
notices when they've stopped keeping a polite distance."

"You can leave it empty. But if you want the world to have that layer — it's there."
```

### `scent` / `setscent`

```
"Related," Sable says. "|wsetscent <text>|n — what you smell like at close range.
Only shows at proximity."

A brief pause. "Cedar. Rain on old wood. Something chemical underneath something
sweet. You know the kind of thing." They look at you steadily. "It's optional. It is,
however, the kind of detail that makes people feel like they're actually in a room
with you."
```

### `sheet` / `look me`

```
"Use |wsheet|n to see everything assembled the way others see it," Sable says. "All
your description fields, your zones, your consent flags. The whole picture."

"|wlook me|n is faster — just your description layers, how you appear on a standard
look." A pause. "Check both. Something always reads differently than you wrote it."
```

### `consent` / `safe` / `safety` / `safeword`

```
"Good question to ask before you have a body," Sable says.

"This world has a consent system. What other characters can do with or around yours —
that's yours to define. You'll have flags you set, categories of interaction you opt
into. None of it is forced."

They hold your gaze. "There's also a safeword. |wsafeword|n, if you type it, stops
everything. No explanation required. No discussion until you're ready for one."

A quieter beat. "Everyone has it. It's not a last resort. It's just a thing you have,
always, in your pocket."
```

### `mirror` / `what's next` / `where am I going`

```
"The Mirror," Sable says. "That's the next space. Where you actually make the
character — name, species, description, all of it. You'll look into it and it'll
show you what you're choosing to be."

They straighten slightly. "If you have questions, ask them now. Once you're in a body
it's harder to see the edges of it clearly. Right now you're still outside looking
in." A pause. "That's a useful place to ask from."
```

### `help`

```
"The things that matter here," Sable says.

"|wsetdesc|n — what you look like. |wsetpresence|n — what people see next to your
name in a room. |wsetbodylang|n — your current posture and activity. |wsetmood|n and
|wsetmoodtell|n — your emotional state and what it looks like on your body.
|wsetproxtell|n — what becomes visible when someone gets close."

"And the communication layer: |wsay <text>|n for your voice. |wpose <action>|n for
your body, in third person."

A final note, quieter: "|wsafeword|n — if you ever need the world to pause."

"When you're ready: |wvoid|n."
```

### `ready` / `next` / `continue`

```
Sable nods once. The quality of it is specific — not dismissal, more like the gesture
of someone sending you somewhere good.

"You're ready," they say.

At the far edge of the space, something that was merely a thickening of the void
shifts and reveals itself: not a door exactly, but a surface. A plane of something
that catches the light you're made of and gives it back to you in a shape you almost
recognize.

The Mirror.

"Whatever you choose to be —" Sable meets your eyes, actually meets them, which is
its own strange thing after lights and stillness "— choose it deliberately. You'll
carry it."

"|wvoid|n. Or |wmirror|n. Either will take you there."
```

---

## What Space 3 Teaches

| Command | How introduced |
|---|---|
| `say` | Greet trigger invites them to try it; parrot fires on use |
| `pose` / `emote` | Parrot redirects to it; pose topic explains |
| `setdesc` | Primary topic — "start here" |
| `setpresence` | Secondary topic — the ambient room impression |
| `setbodylang` | Secondary topic — posture and activity |
| `setmood` + `setmoodtell` | Paired topic — state and its physical tell |
| `setproxtell` | Depth topic — proximity layer teaser |
| `setscent` | Depth topic — optional, introduced lightly |
| `sheet` / `look me` | Check your work |
| `safeword` | Philosophy — normalized, not dramatized |

---

## Guide Arc Note

- **The Witness** — still, ancient. Teaches orientation.
- **Lark** — warm, floating. Teaches wisp identity.
- **Sable** — grounded, dry, embodied. Teaches what a body means and how to write one.

Each one models a different answer to *what are you?*

---

## Build Notes

- `npc.db.react_to_say = True` flag on Sable enables parrot mechanic
- Parrot hook: say command calls `on_hear_say(caller, text)` on NPCs with this flag
- Five parrot responses chosen randomly at runtime — `{text}` = player's said text
- Exit suppressed from room display; revealed by `ready` trigger as "The Mirror"
- Exit key: `void` / aliases: `deeper`, `inward`, `mirror`, `the mirror`, `forward`
- Space 4 is named "The Mirror" — Sable refers to it by name
