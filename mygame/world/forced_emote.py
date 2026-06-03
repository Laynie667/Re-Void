"""
world/forced_emote.py

Forced emote engine for Re:Void.

Broadcasts a pose, say, or emote from a character as if they initiated it —
it appears under their name with their mood color, goes into the scene log
as theirs, and passes through active speech filters.

Used by:
  - DegradingCollar forced begging
  - PermanentBindingCollar periodic humiliation
  - Item periodic_humiliation effect
  - Any future system that needs to speak through a character

Main entry point:
    forced_emote(char, text, emote_type="pose")

emote_type:
    "pose"   — fires as a pose: Name text.
    "say"    — fires through the say verb: Name says, "text."
    "emote"  — fires as a raw emote: text (name prepended if {n} not in text)
    "self"   — private message only, no room broadcast

Speech filters apply to "say" type.
Orgasm denial release word check skipped for forced speech.
"""

import random


def forced_emote(char, text: str, emote_type: str = "pose"):
    """
    Fire a forced emote/say from char.

    Args:
        char:       The character the emote originates from.
        text:       The text to broadcast. For 'say', this is the spoken content.
                    For 'pose'/'emote', this is appended to their name.
        emote_type: "pose" | "say" | "emote" | "self"
    """
    if not char or not text:
        return

    room  = char.location
    name  = char.db.rp_name or char.name

    try:
        from commands.rp_commands import _mood_color
        color = _mood_color(char)
    except Exception:
        color = "|w"

    if emote_type == "self":
        char.msg(f"{color}{text}|n")
        return

    if emote_type == "say":
        # Pass through speech filters
        final_text = text
        try:
            from world.speech_filters import apply_speech_filters
            final_text, blocked, _ = apply_speech_filters(char, text)
            if blocked:
                final_text = text   # forced speech bypasses cant_speak for the item
        except Exception:
            pass
        verb = char.db.say_verb or "says"
        msg  = f'{color}{name} {verb}, "{final_text}"|n'
        char.msg(f'{color}You {verb}, "{final_text}"|n')
        if room:
            room.msg_contents(msg, exclude=char)
            try:
                room.append_scene_log(name, msg)
            except Exception:
                pass

    elif emote_type == "emote":
        if "{n}" in text:
            msg = text.replace("{n}", f"{color}{name}|n")
        else:
            msg = f"{color}{name}|n {text}"
        if room:
            room.msg_contents(f"{msg}|n")
            try:
                room.append_scene_log(name, f"{msg}|n")
            except Exception:
                pass

    else:  # pose (default)
        # Pool messages use {n} as a name token.
        # If text contains {n}, resolve it — that IS the full pose.
        # Otherwise prepend name as normal.
        if "{n}" in text:
            text = text.replace("{n}", name)
            if not text.rstrip().endswith((".", "!", "?", "—", "...")):
                text = text.rstrip() + "."
            msg = f"{color}{text}|n"
        else:
            if text and not text.rstrip().endswith((".", "!", "?", "—", "...")):
                text = text.rstrip() + "."
            msg = f"{color}{name} {text}|n"
        if room:
            room.msg_contents(msg)
            try:
                room.append_scene_log(name, msg)
            except Exception:
                pass


def pick_forced_pool(pools: dict, key: str, fallback_key: str = "default") -> str | None:
    """
    Pick a random message from pools[key], falling back to pools[fallback_key].
    Returns None if both are empty.
    """
    pool = pools.get(key) or pools.get(fallback_key) or []
    return random.choice(pool) if pool else None
