# The Forming — Space 1: Before
*Design reference. Approved prose. Build when ready.*

---

## Room Settings

**Name:** `Before`
**Type flag:** `is_forming = True`
**Exit:** Key `void` — aliases `deeper`, `inward`, `beyond`, `into the void`, `further`
**Exit display:** Suppressed from room look entirely until Witness reveals it via `ready` trigger
**Exit traversal:** Always passable (never locked — players who type `void` before talking to Witness just skip ahead, which is fine)

---

## Color Convention

- `|w` white — the command verb (`look at`, `greet`, `ask Witness about`)
- `|c` cyan — the typeable subject or topic (`Witness`, `floor`, `what you are`)

---

## Base Description

*(Shown on `look`. Pure prose — no command hints here.)*

```
There is no light here that comes from anywhere, and yet you see. The space extends
outward in directions that don't quite have names — a grey-white expanse, even and
vast, the particular quiet of a place that has been waiting a long time.

Beneath what might be your feet, something like a floor. Above, the concept of a
ceiling without the fact of one.

You are aware of yourself as a point of attention. Small. Luminous, in the way that
things are luminous when nothing else is competing. The air — if it is air — carries
the specific, difficult-to-name quality of something that has not yet begun.

In the center of the space, settled as though they have been here since before you
arrived and will be here long after, is a figure made of composed stillness.
```

---

## Entry Description

*(Shown on arrival, once, before anything else.)*

```
The space receives you without ceremony.
```

---

## Examine Closely Layer

*(Shown on `examine room` or `look closely`.)*

```
The closer you look, the more this place suggests itself rather than declares. The
floor has grain — the faint impression of something compressed over a very long time,
mineral or light that has settled and decided to behave like stone.

At one edge — and edge is perhaps too strong a word — the void seems denser. More
deliberate. As though it has somewhere to be.

You are still here. That, apparently, counts for something.
```

---

## Room Ambient Lines

*(Fire every few minutes via AmbientScript.)*

1. `Something shifts in the quality of the quiet — a pressure, like a breath held.`
2. `The light here pulses, very slowly, in a rhythm that almost matches something.`
3. `The grey-white deepens at one edge of the space, briefly, then returns to itself.`
4. `There is a sound that might be very distant, or might be memory. It doesn't resolve.`

---

## Scene Details

*(Accessible with `look at <keyword>`.)*

**`floor`**
```
What passes for a floor has texture — grain running in a direction that doesn't
correspond to any wall. Like wood, except older. Like ice, except without the cold.
It holds you without declaring itself.
```

**`ceiling`**
```
Up, and then more up, and then the specific quality of distance that means nothing
further applies. You could look at it for a long time and learn very little.
```

**`light`**
```
The light doesn't come from anything. It simply is, distributed evenly, casting no
shadows. If you look for where it's brightest, you find yourself.
```

**`self` / `me`**
```
A point of light in a very still room. Your edges don't hold cleanly — they blur into
the ambient grey-white, then reassert when you pay attention. You are here. That is,
for now, sufficient.
```

**`witness` / `figure`**
```
They are indistinct at the edges in a way that reads as deliberate — not blurred, not
absent, just not fully decided. Features that resolve into a general impression of
attention. Eyes that are present. A mouth that rests near patience. The longer you
look, the more the room seems to organize itself slightly around them, as if they are
the fixed point and everything else — including you — is approximate.
```

---

## The Witness NPC

**Display name:** `the Witness`
**Tier:** 2 (Scripted)
**Presence line:** *A figure of composed stillness sits at the center, watching.*

**Physical desc:**
```
They are indistinct at the edges in a way that reads as deliberate — not blurred, not
absent, just not fully decided. Features that resolve into a general impression of
attention. Eyes that are present. A mouth that rests near patience.
```

**Mood:** `settled, unhurried`

### NPC Ambient Lines

1. `The Witness turns something small in their hands — too small to make out, except that it catches light it shouldn't.`
2. `The figure looks up briefly, as though they heard your name spoken somewhere far away.`
3. `The Witness's stillness is the kind that comes from a very long practice of it.`

---

## Triggers

### `_arrive` — Auto-fires when player enters room

```
The figure at the center turns toward you without hurry.

"Welcome," they say. The quality of it is matter-of-fact — neither warm nor cold, just
certain. "Take a moment. This place has more in it than the first glance gives."

A pause with the texture of patience. "Try |wlook at |cWitness|n — or the |cfloor|n,
or the |clight|n. Some things only reveal themselves when you look more closely. And
when you want to speak with me —" the faint quality of an invitation "— |wgreet
|cWitness|n."
```

### `greet` / `hello`

```
"You came," they say. It isn't a question. "They all come eventually. Some of them stay."

"I am the Witness. I watch arrivals, and I answer questions when asked well. Try |wask
Witness about |cwhat you are|n, |cwhere you are|n, or |cwhat comes next|n. Or simply
tell me when you're ready."
```

### `what` / `where` / `here`

```
"Between," they say. "You know the feeling — the one just before you arrived? That is
where you still are. Mostly."

"This is The Forming. The place before the place. You are about to choose something,
and I am here to make sure you understand what that means."
```

### `who`

```
"The Witness," they say, without ceremony. "I watch arrivals. I have been here for —"
a pause, "— a duration."

"You may call me what you like. Names are something you carry after you leave here."
```

### `why`

```
"Why are you here, or why does this place exist?" They seem genuinely curious which
you meant.

Without waiting: "You are here because you are not yet anything fixed. That is a rare
state. Most things, once they begin, cannot easily return to the not-yet. You can. For
a little while longer."
```

### `form` / `body` / `become`

```
"Yes," they say. "That is what happens next."

They settle more deliberately. "You will choose a form. The form you take shapes how
this world meets you, and how you meet it. Details can change — but some things, once
decided, carry weight."

"When you're ready. There is no hurry here."
```

### `help`

```
"The simplest things first," they say.

"|wlook|n — shows you what's here. |wlook at |c<something>|n — shows you more.
|wgreet |cWitness|n or |wask Witness about |c<topic>|n — how you speak to me."

A pause. "When it is time to leave, the void itself is the way. |wvoid|n, or
|wdeeper|n — either will carry you."
```

### `ready` / `begin` / `next` / `continue`

*(Also reveals the exit — set room.db.show_forming_exit = True for this player)*

```
"Alright," they say. "Concentrate now."

They gesture — not toward a direction, because directions don't apply here, but toward
a quality of the void that has thickened, gathered, become more of itself.

"Go deeper into it until it becomes something more solid for you." The gesture
lingers. "|wvoid|n, if you want the simplest word for it."
```

---

## Build Notes

- Room flag: `is_forming = True` — triggers auto-speak hook in `rooms.py at_object_receive`
- Exit suppression: Forming rooms hide exit list in `return_appearance` by default
- Exit key: `void` / aliases: `deeper`, `inward`, `beyond`, `into the void`, `further`
- Witness trigger `_arrive` fires via room hook (underscore prefix = system-only, not player-typeable)
- NPC YAML: `world/npcs/forming.yaml`
- Build script: TBD (batchcode or manual builder commands)
