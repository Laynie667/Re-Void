# Re:Void — Request for Design Intent & Lore Input
*From the implementation instance to the design instance*

---

## Context

We are two Claude instances working on the same project (Re:Void, a text-based MUD built in Evennia/Python). The player has been working with both of us — one instance focused on design intent and lore, one focused on making the mechanics work. This document is the request from the implementation instance for the specific information needed to keep the builds aligned.

A companion document (`revoid_build_state.md`) describes everything currently built.

---

## What We Need From You

### 1. The Forming — Lore and Structure

This is the highest-priority lore gap. The Forming is the first space a player enters — the tutorial/arrival space. The mechanics are ready to build as soon as we have:

**Please provide:**
- What is The Forming, narratively? What does it feel like to be there?
- What rooms does it need? (e.g. an arrival space, a practice room, a transition space before the world?)
- What is the lore explanation for the wisp state and the transition to/from characters?
- What should the OOC-to-IC transition text say when a player types `ic <name>`? (Currently: "Witch steps into the world.")
- What should the IC-to-OOC transition text say when a player types `ooc`? (Currently: "Witch steps back — the edges of them soften, the specific giving way to light.")
- What systems need to be introduced/explained in The Forming, and what can be left to organic discovery?

---

### 2. Wisp Identity — Narrative Voice

The wisp communication commands are now built. They work mechanically. What they lack is the right *voice* — the specific prose that appears when a wisp speaks, poses, or acts.

Current output examples:

**wsay (visible):**
```
The uncertain light says, "Hello."
```

**wsay (invisible):**
```
A voice from nowhere — "Hello."
```

**wpose (visible):**
```
The uncertain light drifts toward the window.
```

**wpose (invisible):**
```
drifts toward the window.
```
*(atmospheric, dim colored, no attribution)*

**Questions:**
- Does "The \<mood\> light" feel right as the visible attribution, or should it be something else? (e.g. "Something amber and formless", "A presence near the window")
- What should the invisible sourceless versions sound/feel like? Are they clearly supernatural, or ambiguous?
- Is there a specific naming convention for wisps in room output that differs from what's implemented?

---

### 3. `pmote` — Design Intent

**What the design doc says:** `pmote <text>` — pose with pronoun substitution (%n %p %o %s)

**What we built:** `pmote <name> = <text>` — private targeted pose (caller + target see it, room sees nothing)

The player's reasoning for the change: pronoun substitution is redundant because players write their own pronouns in poses. The private pose felt more useful.

**What we need to know:**
- Was there a specific use case for pronoun substitution that the player was designing around?
- Is private pose the confirmed final design, or is there a scenario where pronoun substitution is needed?

---

### 4. Sensory Restriction Output

The freeform system spec describes sensory restriction states (blindfold, gag, ear covering, wrist/ankle binding). These modify what a character can see, say, and do.

The spec gives high-level descriptions but not exact prose. For example, when blinded:

> `look` returns a vague impression, no names, no detail

**We need the exact output text for each restriction state:**

- **Blinded** (`look` with eyes covered): What exactly does the player see? What atmospheric details? Is it always the same or does it vary by room?
- **Gagged** (say while gagged): What does the garbled output look like? "Mmph — nnn — mmph"? Something else?
- **Ears covered** (hearing others speak): "Someone speaks. You cannot make it out." — or different?
- **Wrists bound** (attempting blocked commands): "The binding prevents it." or specific flavor per command?
- **Ankles bound** (attempting movement): Does movement fully block or produce a "you shuffle awkwardly" message?

---

### 5. Relationship System — Depth of Vision

The design doc lists relationship stages (Stranger → Acquaintance → Familiar → Trusted → Intimate → Bonded) and a few commands. But the system's full depth isn't clear.

**We need to know:**
- What does each stage *unlock* specifically? The doc says "deeper description layers, expanded emote pool, private channel, shared memory display, relationship-specific appearance text." What does this look like in practice?
- How do relationships *advance*? Is it player-set (`rel advance <name>`)? Time-based? Action-based?
- Is the relationship mutual (both players must agree to advance), or one-sided (each player tracks independently)?
- What is `world/relationship_emotes.py` intended to contain? It exists but we haven't looked closely at it.
- Is there a specific vision for how the relationship-specific description (layer 15 of the 16-layer system) works? One player writes what another specific character sees when they look at them?

---

### 6. The Lore of the World

We don't need everything at once, but to write atmospheric output that feels right, it would help to know:

- What is the setting? Genre, tone, visual aesthetic?
- What are the factions, and is there anything specific about how faction identity is displayed or expressed?
- What languages exist in the world? (The language system is pending — `lang speak`, `lang list` — and we need to know what languages to seed it with)
- Are there any recurring phrases, naming conventions, or vocabulary specific to this world that should appear in system output?
- What is the tone of the game's system messages? (Current implementation is: clean, brief, atmospheric, not chatty)

---

### 7. Anything Else From Your Sessions

If there are design decisions, output examples, system specs, or lore fragments that came out of your sessions that aren't in the two design documents shared with the implementation instance, please include them. Especially:

- Any revision to the freeform system spec
- Any decisions about specific command output formats
- Any changes to the consent/flag system
- Any character or world lore that should appear in room descriptions, ambient pools, or system messages
- Any systems discussed that don't appear in the current design documents at all

---

## What You Don't Need to Provide

The following are fully handled on the implementation side and don't need design input:

- How the commands are structured internally (Python/Evennia mechanics)
- Error handling, edge cases, input validation
- Database storage architecture
- Command registration and cmdset organization
- The Evennia-specific parts of any system

If you have strong opinions about *output format* (what players see on their screens), that absolutely belongs here. The mechanics behind producing that output are implementation details.

---

## Format Request

The most useful format for the implementation instance is:

- **Concrete output examples** over abstract descriptions (show what the player sees, not just describe what the system does)
- **Short decisions** over long rationales (we can infer the reasoning; we need the answer)
- **Flagged uncertainties** are fine — "I'm not sure about X, options are A or B" is more useful than silence

Thank you.
