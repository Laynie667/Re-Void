"""
commands/zone_interact_commands.py

Zone interaction commands — trigger handle message pools on character zones.

The exact verb typed (touch, kiss, grope, etc.) becomes the pool key, so
a character can set different messages for each interaction type on each zone.

Usage:
    <verb> <target>                — interact with target (zone auto-selected)
    <verb> <target> <zone>         — interact with target's specific zone
    <verb>/quiet <target> [zone]   — silent to the room (actor + target only)
    <verb>/private <target> [zone] — target receives it, room sees nothing
    <verb>/self <target> [zone]    — actor sees a private self-note only

Available verbs (all dispatch to the same handler):
    touch, caress, grope, stroke, grab, squeeze,
    kiss, bite, lick, taste, pull, pinch, nuzzle, hold, pet

If the target has no handle messages set for that verb on that zone,
a fallback generic action is emitted instead.

Message tokens (replaced at output time):
    {actor}        — the actor's rp_name (person doing the action)
    {actor_s}      — actor's possessive name  ("Kira's")
    {actor_they}   — actor's subject pronoun  (he / she / they)
    {actor_them}   — actor's object pronoun   (him / her / them)
    {actor_their}  — actor's possessive pronoun (his / her / their)
    {actor_ref}    — actor's reflexive pronoun (himself / herself / themselves)
    {target}       — the target's rp_name
    {target_s}     — target's possessive name  ("Helena's")
    {target_they}  — target's subject pronoun
    {target_them}  — target's object pronoun
    {target_their} — target's possessive pronoun
    {target_ref}   — target's reflexive pronoun
    {zone}         — the zone name (spaces, not underscores)

Example setup (on the target's character):
    zone handle/add neck/touch = {actor} traces a slow line along
    {target_s} neck with one finger.

Example use:
    touch helena neck
    grope/quiet lark chest
    kiss/private sorrel lips
"""

import random
from evennia import Command


# ---------------------------------------------------------------------------
# Verb display names (for fallback messages)
# ---------------------------------------------------------------------------

_VERB_DISPLAY = {
    "touch":   "touches",
    "caress":  "caresses",
    "grope":   "gropes",
    "stroke":  "strokes",
    "grab":    "grabs",
    "squeeze": "squeezes",
    "kiss":    "kisses",
    "bite":    "bites",
    "lick":    "licks",
    "taste":   "tastes",
    "pull":    "pulls at",
    "pinch":   "pinches",
    "nuzzle":  "nuzzles",
    "hold":    "holds",
    "pet":     "pets",
}


# ---------------------------------------------------------------------------
# Token resolver
# ---------------------------------------------------------------------------

def _possessive_name(name):
    """Return 'Name's' (or 'Names'' if name ends in s)."""
    if name.endswith("s"):
        return f"{name}'"
    return f"{name}'s"


def _resolve_tokens(text, actor, target, zone_display):
    """
    Replace pronoun and name tokens in a handle message.

    Args:
        text (str):    The raw message from the pool.
        actor:         Character doing the action.
        target:        Character being interacted with.
        zone_display:  Zone name with spaces (for {zone} token).
    """
    def _pronouns(char):
        p = getattr(char.db, "pronouns", None) or {}
        return {
            "subject":   p.get("subject",   "they"),
            "object":    p.get("object",     "them"),
            "possessive": p.get("possessive", "their"),
            "reflexive": p.get("reflexive",  "themselves"),
        }

    actor_name  = actor.db.rp_name  or actor.name
    target_name = target.db.rp_name or target.name
    ap = _pronouns(actor)
    tp = _pronouns(target)

    return (
        text
        .replace("{actor}",        actor_name)
        .replace("{actor_s}",      _possessive_name(actor_name))
        .replace("{actor_they}",   ap["subject"])
        .replace("{actor_them}",   ap["object"])
        .replace("{actor_their}",  ap["possessive"])
        .replace("{actor_ref}",    ap["reflexive"])
        .replace("{target}",       target_name)
        .replace("{target_s}",     _possessive_name(target_name))
        .replace("{target_they}",  tp["subject"])
        .replace("{target_them}",  tp["object"])
        .replace("{target_their}", tp["possessive"])
        .replace("{target_ref}",   tp["reflexive"])
        .replace("{zone}",         zone_display)
    )


# ---------------------------------------------------------------------------
# Zone resolver — finds a zone on the target
# ---------------------------------------------------------------------------

def _find_zone(target, zone_query):
    """
    Find a zone on target by name (exact or prefix match).
    Returns (zone_name, zone_data) or (None, None).
    """
    if hasattr(target, "_get_zones"):
        zones = target._get_zones()
    else:
        zones = getattr(target.db, "zones", None) or {}

    if not zones:
        return None, None

    # Exact match
    key = zone_query.lower().replace(" ", "_").replace("-", "_")
    if key in zones:
        zd = zones[key]
        if hasattr(zd, "items"):
            zd = dict(zd)
        return key, zd

    # Prefix match on full path
    for zname, zdata in zones.items():
        if zname.startswith(key):
            if hasattr(zdata, "items"):
                zdata = dict(zdata)
            return zname, zdata

    # Leaf-name match — e.g. "pussy" matches "groin/pussy"
    for zname, zdata in zones.items():
        leaf = zname.split("/")[-1]
        if leaf == key or leaf.startswith(key):
            if hasattr(zdata, "items"):
                zdata = dict(zdata)
            return zname, zdata

    return None, None


# ---------------------------------------------------------------------------
# CmdZoneInteract
# ---------------------------------------------------------------------------

class CmdZoneInteract(Command):
    """
    Interact with another character's body zone.

    Usage:
      <verb> <target>
      <verb> <target> <zone>
      <verb>/quiet <target> [zone]    — actor + target see it; room silent
      <verb>/private <target> [zone]  — only target sees it
      <verb>/self <target> [zone]     — only you see a private note

    Available verbs:
      touch, caress, grope, stroke, grab, squeeze,
      kiss, bite, lick, taste, pull, pinch, nuzzle, hold, pet

    If the target has set handle messages for that verb on that zone,
    one is chosen at random and broadcast with their pronouns and names
    filled in. Otherwise a generic action is used.

    Message tokens (for setting handle messages with zone handle/add):
      {actor}        — actor's name
      {actor_s}      — actor's possessive name ("Kira's")
      {actor_they}   — actor's subject pronoun
      {actor_them}   — actor's object pronoun
      {actor_their}  — actor's possessive pronoun
      {actor_ref}    — actor's reflexive pronoun
      {target}       — target's name
      {target_s}     — target's possessive name
      {target_they}  — target's subject pronoun
      {target_them}  — target's object pronoun
      {target_their} — target's possessive pronoun
      {target_ref}   — target's reflexive pronoun
      {zone}         — zone name

    See also: zone handle/add, zone handle/list
    """

    key      = "touch"
    aliases  = [
        "caress", "grope", "stroke", "grab", "squeeze",
        "kiss",   "bite",  "lick",   "taste",
        "pull",   "pinch", "nuzzle", "hold", "pet",
    ]
    locks    = "cmd:all()"
    help_category = "RP Tools"
    switch_options = ("quiet", "private", "self")

    def parse(self):
        """
        Extract /switches from the cmdstring before func() runs.
        Base Command does not parse switches — we do it here so that
        'kiss/quiet helena' works the same as it would on a MuxCommand.
        """
        super().parse()
        if "/" in self.cmdstring:
            parts = self.cmdstring.split("/")
            # Leave cmdstring as just the verb (e.g. "kiss")
            self.cmdstring = parts[0].strip()
            self.switches = [s.strip().lower() for s in parts[1:] if s.strip()]
        else:
            self.switches = []

    def func(self):
        caller = self.caller
        verb   = self.cmdstring.lower()  # exact verb typed
        args   = self.args.strip()
        switches = self.switches

        if not args:
            caller.msg(
                f"|xUsage: {verb} <target> [zone]|n\n"
                f"|xSwitches: /quiet /private /self|n"
            )
            return

        # ── Parse target and optional zone ────────────────────────
        # Format: '<target>' or '<target> <zone>' or '<target> <zone words>'
        # We try to find the target first, then treat the remainder as zone.
        words = args.split()
        target = None
        zone_query = None

        # Try progressively longer target strings (1 word, then 2, etc.)
        for split_at in range(1, len(words) + 1):
            target_str = " ".join(words[:split_at])
            candidate = caller.search(target_str, quiet=True)
            if isinstance(candidate, list):
                candidate = candidate[0] if candidate else None
            if candidate:
                target = candidate
                remainder = words[split_at:]
                zone_query = "_".join(remainder).lower() if remainder else None
                break

        if not target:
            # Fallback: check if args looks like a zone on the caller
            # e.g. "grope pussy" → grope self's pussy zone
            zone_test = args.lower().replace(" ", "_")
            caller_zones = getattr(caller.db, "zones", None) or {}
            matched_zone = None
            if zone_test in caller_zones:
                matched_zone = zone_test
            else:
                # Leaf-name match
                for zn in caller_zones:
                    if zn.split("/")[-1] == zone_test or zn.split("/")[-1].startswith(zone_test):
                        matched_zone = zn
                        break
            if matched_zone:
                target = caller
                zone_query = matched_zone
            else:
                caller.msg(f"|xYou don't see '{args}' here.|n")
                return

        # ── Resolve zone ──────────────────────────────────────────
        zone_name = None
        zone_data = None

        if zone_query:
            zone_name, zone_data = _find_zone(target, zone_query)
            if not zone_name:
                caller.msg(
                    f"|x{target.db.rp_name or target.name} doesn't "
                    f"have a zone called '{zone_query}'.|n"
                )
                return
        else:
            # No zone specified — try to find any zone with handle
            # messages for this verb; fall back to first visible zone
            if hasattr(target, "_get_zones"):
                zones = target._get_zones()
            else:
                zones = getattr(target.db, "zones", None) or {}

            for zn, zd in zones.items():
                if not hasattr(zd, "get"):
                    continue
                handles = zd.get("handle_details", {}) or {}
                if hasattr(handles, "items"):
                    handles = dict(handles)
                if verb in handles and handles[verb]:
                    zone_name = zn
                    zone_data = dict(zd) if hasattr(zd, "items") else zd
                    break

            # Still nothing — default to "body" or first zone
            if not zone_name and zones:
                zone_name = next(iter(zones))
                zd = zones[zone_name]
                zone_data = dict(zd) if hasattr(zd, "items") else zd

        # ── Pick a message ────────────────────────────────────────
        zone_display = (zone_name or "body").replace("_", " ")
        message = None

        if zone_data:
            handles = zone_data.get("handle_details", {}) or {}
            if hasattr(handles, "items"):
                handles = dict(handles)
            pool = list(handles.get(verb, []) or [])
            if pool:
                raw = random.choice(pool)
                message = _resolve_tokens(raw, caller, target, zone_display)

        # Fallback generic message
        if not message:
            actor_name  = caller.db.rp_name or caller.name
            target_name = target.db.rp_name or target.name
            verb_display = _VERB_DISPLAY.get(verb, verb + "s")
            message = (
                f"{actor_name} {verb_display} "
                f"{target_name}'s {zone_display}."
            )

        # ── Broadcast ────────────────────────────────────────────
        quiet   = "quiet"   in switches
        private = "private" in switches
        self_sw = "self"    in switches
        room    = caller.location

        if self_sw:
            # Actor-only, no broadcast
            caller.msg(f"|x[private] {message}|n")
            return

        if private:
            # Target only — actor sees a note, room silent
            target.msg(message)
            caller.msg(f"|x[private → {target.db.rp_name or target.name}] {message}|n")
            return

        if quiet:
            # Actor + target only
            caller.msg(message)
            if target != caller:
                target.msg(message)
            return

        # Default: broadcast to room
        if room:
            room.msg_contents(message)
        else:
            caller.msg(message)


# ---------------------------------------------------------------------------
# CmdSmell — perception command, shows scent_desc of a target
# ---------------------------------------------------------------------------

class CmdSmell(Command):
    """
    Smell yourself or another character.

    Usage:
      smell           — smell yourself
      smell <target>  — smell someone nearby
      sniff <target>  — alias

    Shows the scent description set via setscent.
    """

    key     = "smell"
    aliases = ["sniff"]
    locks   = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        args   = self.args.strip()

        if args:
            # Search in room + self
            target = caller.search(args, quiet=True)
            if isinstance(target, list):
                target = target[0] if target else None
            if not target:
                caller.msg(f"|xYou don't see '{args}' here.|n")
                return
        else:
            target = caller

        scent = getattr(target.db, "scent_desc", None) or ""
        target_name = (getattr(target.db, "rp_name", None) or target.name)

        if scent:
            if target == caller:
                caller.msg(f"|xYou smell yourself — {scent}.|n")
            else:
                caller.msg(
                    f"|xYou breathe in. {target_name} — {scent}.|n"
                )
        else:
            if target == caller:
                caller.msg("|xYou don't notice anything particular about your own scent.|n")
            else:
                caller.msg(
                    f"|x{target_name} doesn't have a notable scent.|n"
                )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_ZONE_INTERACT_CMDS = [CmdZoneInteract, CmdSmell]
