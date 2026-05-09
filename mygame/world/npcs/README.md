# Re:Void NPC Definitions

Place `.yaml` files here to define NPCs. Each file can contain multiple NPCs.
Load them in-game with:

    npc load world/npcs/<filename>.yaml
    npc loadall world/npcs

## Example file structure

```yaml
npcs:
  - id: "example_npc"        # unique id for lookup — use npc sheet example_npc
    name: "The Example"
    tier: 2                  # 1=ambient 2=scripted 3=interactive
    location: "#1234"        # room dbref

    desc:
      physical: "A figure of middling height..."
      outfit:   "They wear something unremarkable."
      mood:     "pleasantly neutral"
      presence: "An air of deliberate stillness."

    ambient:
      base:
        - "The Example adjusts their collar absently."
        - "The Example's gaze drifts to the doorway."

    triggers:
      hello:
        type: say
        response: "The Example tilts their head. 'Hello.'"
        set_state:
          greeted: true
      help:
        type: say
        response:
          - "The Example considers this for a moment."
          - "The Example says nothing, but gestures toward the door."
        conditions:
          greeted: true

    lore_fields:
      - name: "Role"
        value: "Placeholder"
```

## Tiers

- **Tier 1 — Ambient**: Shows up in the room, contributes ambient lines. Not interactive.
- **Tier 2 — Scripted**: Has triggers (`ask <npc> about <keyword>`) and optional services (`nservice`).
- **Tier 3 — Interactive**: Full zone system, consent flags, lore sheet.
