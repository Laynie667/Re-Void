# Adding Cards to Re:Void's Cards Against Humanity

All card content lives in YAML files inside `world/cah/`. This guide explains every step.

---

## YAML Format

### White Cards (answer cards)
White cards are plain strings in a list:

```yaml
cards:
  - "A horse-sized duck"
  - "Unexplained guilt"
  - "The audacity"
```

Each entry is just a short phrase, noun, or description. Keep them punchy — ideally
under 10 words. They need to work as an answer dropped into a black card's blank.

### Black Cards (prompt cards)
Black cards are objects with `text` and `pick` keys:

```yaml
cards:
  - text: "What's that smell?"
    pick: 1
  - text: "Scientists discovered that _ is responsible for _."
    pick: 2
```

- `text`: The prompt. Use `_` as a placeholder for each blank.
- `pick`: How many white cards players must play. Must equal the number of `_` in the text.
  - `pick: 1` — one blank, players play one card
  - `pick: 2` — two blanks, players play two cards (submitted in order)

**Rule:** The number of `_` characters in `text` MUST match `pick`. If they don't match
the game will still run, but the display will be confusing.

---

## Adding Cards to an Existing Deck

Open any of the existing YAML files and append entries to the `cards:` list.

### Example: Adding 5 cards to `base_white.yaml`

```yaml
  - "A very strong opinion about soup"
  - "The confidence of someone who has never been audited"
  - "A cat watching you make a bad decision"
  - "The void, but make it cozy"
  - "Definitely not a cult, but the vibes are similar"
```

### Example: Adding 5 cards to `base_black.yaml`

```yaml
  - text: "I've been productive today. I _ for three hours."
    pick: 1
  - text: "What does the sign in my soul say?"
    pick: 1
  - text: "The job interview went fine until I mentioned _."
    pick: 1
  - text: "The reunion was going well until someone brought up _ and _."
    pick: 2
  - text: "My legacy will be _."
    pick: 1
```

---

## Creating a New Deck File

1. Create two new files in `world/cah/`:
   - `mydeckname_black.yaml` — prompt cards
   - `mydeckname_white.yaml` — answer cards

2. Both files must start with `cards:` and list entries underneath.

**Example `seasonal_black.yaml`:**
```yaml
cards:
  - text: "This holiday season, I am most grateful for _."
    pick: 1
  - text: "The worst part of the holidays is _ followed immediately by _."
    pick: 2
```

**Example `seasonal_white.yaml`:**
```yaml
cards:
  - "The gift nobody wanted but everyone got"
  - "Mandatory fun"
  - "A fruitcake with a backstory"
```

---

## Registering the New Deck in cah_loader.py

Open `world/cah_loader.py` and find the `DECK_REGISTRY` dict. Add your deck:

```python
DECK_REGISTRY = {
    "base": { ... },
    "nsfw": { ... },
    "revoid": { ... },
    # Add your new deck here:
    "seasonal": {
        "black": "seasonal_black.yaml",
        "white": "seasonal_white.yaml",
        "description": "Holiday-themed cards",
    },
}
```

Once registered, players can include it when starting a game:

```
cah start base nsfw revoid seasonal
```

Or you can add it to `DEFAULT_DECKS` in `cah_loader.py` so it loads automatically:

```python
DEFAULT_DECKS = ["base", "nsfw", "revoid", "seasonal"]
```

---

## Tips

- White cards work best as noun phrases or short descriptions, not full sentences.
- Black cards with `pick: 2` are the most fun when the two blanks create a cause/effect
  or contrast relationship.
- ReVoid-themed cards hit hardest when they reference specific cabin details — the
  wolves, the chest, the ice palace, the cables, Helena's look.
- Test new cards in-game with `cah start` before committing them permanently.
