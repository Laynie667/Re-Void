# The Forming — Space 2: The Drift
*Design reference. Approved prose. Build when ready.*

---

## Room Settings

**Name:** `The Drift`
**Type flag:** `is_forming = True`
**Exit:** Key `void` — aliases `deeper`, `inward`, `beyond`, `into the void`, `further`
**Exit display:** Suppressed until Lark reveals it via `ready` trigger

---

## Color Convention

- `|w` white — command verb (`wdesc`, `wcolor`, `look at`, `ask Lark about`)
- `|c` cyan — typeable subject or topic (`Lark`, `desc`, `color`, `wisp`)

---

## Base Description

```
The grey-white has changed. Not into something, exactly — into a place where
something is possible.

There is still no ceiling, no floor that declares itself, no walls with opinions
about their own existence. But there is company.

Other lights drift through the space at varying distances. Some are still. Some move
with the slow deliberateness of things going somewhere without caring when they
arrive. They are small — smaller than you expected — and each one is subtly
particular. This one trails warmth. That one carries a faint sound at its edges, a
frequency you almost recognize.

You are one of these. This is what you look like from the outside: a point of
attention, drifting in the same space, just as particular and just as hard to fully
describe.

Near the center, one light is more deliberate than the others. It has the quality of
something that has been waiting, specifically, for you.
```

---

## Entry Description

```
The drift receives you. Several lights take brief notice, then return to wherever
they were going.
```

---

## Examine Closely Layer

```
Each light here is different in ways that resist summary. Some have a sound at their
edges. Some shift color when they move. Some seem larger up close than from a
distance, and smaller again when you stop looking directly at them.

You are trying to see yourself from the outside. It's difficult. You keep catching
the edges of what you must look like — a particular quality of light, something
distinctly yours — but the center of it keeps moving when you reach for it.

That's fine. That's what this space is for.
```

---

## Room Ambient Lines

1. `A pale silver light drifts past, trailing something like a half-remembered melody.`
2. `At the far edge, two lights press briefly together, then separate.`
3. `Something small and very bright crosses the space too quickly to follow.`
4. `The air here holds the impression of many presences, most of them elsewhere.`
5. `One of the lights nearby brightens momentarily — emphasis, or acknowledgment, or just the nature of light.`

---

## Scene Details

**`others` / `lights` / `wisps`**
```
Each one particular. This one carries warmth at its edges. That one moves with the
specific quality of impatience. A third holds very still, watching something you
can't see. You are one of these. The thought arrives without fanfare.
```

**`lark` / `amber`**
```
Warm amber, slightly larger than average, with the settled radiance of something that
has been a light for a long time. At its edges, a faint sound — almost musical,
almost not. It drifts without urgency, in the way of things that have stopped being
impatient.
```

**`self` / `me`**
```
You are a point of light in a space full of other points of light. From the outside —
you understand this now — you look like this: particular, drifting, not yet fully
decided. The color of you is whatever you've chosen, or haven't yet. The impression
of you is yours to write. That is the only thing being asked of you here.
```

**`sound` / `music` / `frequency`**
```
Some wisps carry a sound. Not music exactly — more like the memory of a frequency,
or the suggestion of one. You could have this. It would be yours.
```

---

## Lark NPC

**Display name:** `Lark`
**Tier:** 2 (Scripted)
**Presence line:** *A warm amber light hovers nearby, trailing something almost like music at its edges.*
**Mood:** `fond, unhurried, slightly delighted`

**Physical desc:**
```
Warm amber, slightly larger than the other wisps drifting through, with the particular
settled radiance of something that has been a light for a long time. At its edges —
barely audible, just past the threshold of imagining — a faint sound. Almost musical.
Almost not.
```

### Lark Ambient Lines

1. `Lark drifts in a slow idle circle, the way some people pace while they think.`
2. `The amber light brightens briefly — the wisp equivalent of a smile, you suspect.`
3. `Lark holds very still for a moment, then resumes moving. Whatever it was, it passed.`

---

## Triggers

### `_arrive` — Auto-fires on entry

```
The amber light turns toward you before you've fully arrived, and you get the
impression — somehow — that it's smiling.

"Oh, a new one," it says. The voice is warm, slightly amused by something pleasant.
"Hello, you. Welcome to what you are."

A pause that feels fond. "You're a wisp. We all are, until we decide to be something
more solid — and even then, most of us keep it. It's useful. It's ours."

"I'm Lark. I've been a wisp longer than I've been anything else." A small idle drift.
"|wlook at |cLark|n, if you want to see what identity looks like on someone who's had
a while to settle into it. And |wask Lark about |cwisp|n when you're ready to
understand what you are."
```

### `greet` / `hello`

```
"Hello again," Lark says, warmly. "Look around — these are your people, more or
less. All lights. All particular. All going somewhere eventually."

"You'll want to know what you look like to the rest of us. |wask Lark about |cdesc|n
or |ccolor|n — that's where most people start."
```

### `what` / `wisp` / `what am I`

```
"A wisp," Lark says, with the ease of something said many times without getting tired
of it. "A presence without a body. You can move through spaces, observe, communicate
— other wisps can see you, and certain characters will notice you too, depending on
where you are."

"You're not nothing. You're just not solid yet." A beat, warm. "Solid comes later.
There's no rush."
```

### `desc` / `wdesc` / `description`

```
"Your wisp description," Lark says. "The short impression of what you look like to
everyone else in the drift. Not a body — just a quality. A color, a texture, a sound,
a feeling. Whatever fits."

"Use |wwdesc|n to write it. A line or two. You can change it anytime — this is not a
permanent decision. Just a starting point."
```

### `color` / `wcolor`

```
"The color of your light," Lark says. "It shows when you speak, when you drift, when
someone looks at you. It's the fastest way to be recognizable."

"Use |wwcolor|n and give it a name. |ccrimson|n, |cpale blue|n, |cgold|n, |cthe
particular grey of early morning|n — whatever feels like you. Evocative language
works."
```

### `size` / `wsize`

```
"How much space you take up," Lark says. "Some wisps are very small and very focused.
Some are large and diffuse. Neither is better — just a different quality of presence."

"|wwsize|n, then a word or phrase. |csmall|n, |cvast|n, |ctinier than most|n —
describe it however you like."
```

### `signature` / `wsignature` / `ambient`

```
"The line that follows you," Lark says. "An ambient impression — what people notice
when you drift through a room without speaking. Some wisps have a sound. Some have a
smell. Some have a feeling, like pressure or warmth or the specific quality of being
watched by something that wishes you well."

"|wwsignature|n. One line, evocative. Something that's distinctly yours — not what
you look like, but what you leave behind when you pass through."
```

### `preview` / `wpreview`

```
"Once you've set a few things, |wwpreview|n will show you how you appear to everyone
else in the drift. It's useful to check before you go somewhere you care about."

A fond drift. "Some wisps spend a long time on it. That's not a flaw."
```

### `character` / `body` / `form` / `ic`

```
"Later," Lark says, not unkindly. "You'll make a character — a real body, a name, a
face, a history you choose. That's what the rest of The Forming is for."

"But your wisp comes first. Your account is your wisp. Your character is something
you put on — and take off, when you need to come back to yourself." A pause. "A lot
of people find that useful. The coming back."
```

### `help`

```
"Right," Lark says. "The things you can do as a wisp:"

"|wwdesc|n — what you look like to others. |wwcolor|n — the color of your light.
|wwsize|n — how much space you take. |wwsignature|n — the impression you leave when
you pass through a room."

"None of it permanent. All of it yours." A small idle drift. "When you're done
exploring — |wvoid|n moves you on."
```

### `ready` / `next` / `continue`

```
"Already?" Lark sounds pleased rather than surprised. "Good instinct."

The amber light drifts toward one edge of the space where the drift has thinned,
pointing somewhere with its quality of attention rather than with any gesture.

"The next space gets more specific. You're going to start choosing things that last."
A warm, brief brightening. "You're doing well. |wvoid|n when you're ready."
```

---

## Build Notes

- Ambient NPC wisps (Tier 1, no triggers) drift through the room — several instances, each with one unique ambient line, no interaction. They exist to show that wisps are real presences.
- Lark is Tier 2. Only Lark has triggers.
- Exit suppressed from room display until `ready` fires
- Same `void`/`deeper` exit key structure as Space 1
