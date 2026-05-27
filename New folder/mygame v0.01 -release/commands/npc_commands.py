"""
commands/npc_commands.py

NPC and Scene Extra commands for Re:Void.

BUILDER COMMANDS  (perm: Builder)
----------------------------------
npc list [here]                     — list all NPCs or only those in room
npc create <name> [tier=N]          — create an NPC in current room
npc load <yaml_file>                — load NPCs from a YAML file
npc loadall [dir]                   — load all YAML from a directory
npc set <npc> <field> = <value>     — set a desc field (physical/outfit/mood/presence)
npc tier <npc> <1-3>                — change NPC tier
npc ambient <npc> add <line>        — add a base ambient line
npc ambient <npc> list              — list ambient lines
npc ambient <npc> clear             — clear all base ambient lines
npc trigger <npc> <kw> = <response> — add/update a trigger keyword
npc trigger <npc> <kw> /clear       — remove a trigger keyword
npc service <npc> <name> = <desc>   — add/update a service
npc service <npc> <name> /clear     — remove a service
npc lore <npc> <name> = <value>     — add/update a lore field
npc sheet <npc>                     — view full NPC builder sheet
npc remove <npc>                    — delete an NPC permanently

SCENE EXTRA COMMANDS  (all players)
-------------------------------------
extra create <name> [= <desc>]      — create a scene extra in current room
extra say <name> = <text>           — make your extra say something
extra pose <name> = <text>          — make your extra do something
extra emote <name> = <text>         — alias for pose
extra whisper <name> = <text>       — quiet, italic extra action
extra remove <name>                 — remove one of your scene extras
extras                              — list scene extras in the room
extra list                          — same

NPC INTERACTION COMMANDS  (all players)
----------------------------------------
greet <npc>                         — trigger the NPC's greeting
ask <npc> about <keyword>           — trigger a keyword response
nservice <npc>                      — list NPC's available services
nservice <npc> <service>            — request a specific service

Scene extras auto-clean when a scene ends. Builders can also
remove any extra with 'extra remove'. Each player can manage
only the extras they created (unless Builder+).
"""

import time
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import search as ev_search


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _char(caller):
    """Return the character entity regardless of caller type."""
    return caller.puppet if hasattr(caller, 'puppet') else caller


def _find_npc_in_room(char, name):
    """
    Find an NPC by name in char's current room.
    Checks rp_name and key — prefix match OR substring match
    so "witness" finds an NPC whose rp_name is "the Witness".
    Returns NPC object or None.
    """
    from typeclasses.npc import NPC
    room = char.location
    if not room:
        return None
    name_lower = name.strip().lower()
    for obj in room.contents:
        if not isinstance(obj, NPC):
            continue
        display = (obj.db.rp_name or obj.key or "").lower()
        key_lower = obj.key.lower()
        if (display.startswith(name_lower)
                or name_lower in display
                or key_lower.startswith(name_lower)
                or name_lower in key_lower):
            return obj
    return None


def _find_npc_global(name):
    """
    Find an NPC anywhere in the world by name, id tag, or dbref.
    Returns first match or None.
    """
    from typeclasses.npc import NPC

    # dbref?
    if name.startswith("#"):
        results = ev_search.search_object(name, typeclass=NPC)
        return results[0] if results else None

    # id tag?
    from evennia import search_tag
    from world.npc_loader import NPC_TAG_CATEGORY
    tagged = search_tag(name, category=NPC_TAG_CATEGORY)
    if tagged:
        return tagged[0]

    # name search
    results = ev_search.search_object(name, typeclass=NPC)
    return results[0] if results else None


def _get_extras(room):
    """Return room.db.scene_extras, initialising if needed."""
    if not room:
        return {}
    return room.db.scene_extras or {}


def _save_extras(room, extras):
    room.db.scene_extras = extras


def _find_extra(room, name):
    """
    Find a scene extra by name (case-insensitive prefix).
    Returns (canonical_name, extra_dict) or (None, None).
    """
    name_lower = name.strip().lower()
    extras = _get_extras(room)
    for key, data in extras.items():
        if key.lower().startswith(name_lower):
            return key, data
    return None, None


# -----------------------------------------------------------------------
# Builder NPC command
# -----------------------------------------------------------------------

class CmdNPC(MuxCommand):
    """
    Manage NPCs. Builder permission required.

    Usage:
        npc list [here]                     — list NPCs (room or world)
        npc create <name> [tier=N]          — create NPC here (tier 1-3)
        npc load <yaml_file>                — load NPCs from YAML
        npc loadall [dir]                   — load all YAML in directory
        npc set <npc> <field> = <value>     — set desc field
        npc tier <npc> <1-3>                — change tier
        npc ambient <npc> add <line>        — add ambient line
        npc ambient <npc> list              — list ambient lines
        npc ambient <npc> clear             — clear all ambient lines
        npc trigger <npc> <kw> = <response> — add/update trigger
        npc trigger <npc> <kw>/clear        — remove trigger
        npc service <npc> <name> = <desc>   — add/update service
        npc service <npc> <name>/clear      — remove service
        npc lore <npc> <name> = <value>     — add/update lore field
        npc sheet <npc>                     — view NPC sheet
        npc remove <npc>                    — delete NPC permanently

    Field names for 'npc set':
        physical / outfit / mood / presence

    Tiers:
        1 = Ambient (ambient lines only)
        2 = Scripted (triggers + services)
        3 = Interactive (zones + lore + consent handling)

    Triggers fire on 'ask <npc> about <keyword>'.
    Services fire on 'nservice <npc> <name>'.

    See also: extra, greet, ask, nservice
    """
    key = "npc"
    locks = "cmd:perm(Builder)"
    help_category = "Builder"

    SET_FIELDS = ("physical", "outfit", "mood", "presence")

    def func(self):
        char = _char(self.caller)
        args = self.args.strip()

        if not args or args == "list":
            self._npc_list(char, here=False)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest   = parts[1].strip() if len(parts) > 1 else ""

        dispatch = {
            "list":    lambda: self._npc_list(char, here=(rest == "here")),
            "create":  lambda: self._npc_create(char, rest),
            "load":    lambda: self._npc_load(rest),
            "loadall": lambda: self._npc_loadall(rest or "world/npcs"),
            "set":     lambda: self._npc_set(char, rest),
            "tier":    lambda: self._npc_tier(char, rest),
            "ambient": lambda: self._npc_ambient(char, rest),
            "trigger": lambda: self._npc_trigger(char, rest),
            "service": lambda: self._npc_service(char, rest),
            "lore":    lambda: self._npc_lore(char, rest),
            "sheet":   lambda: self._npc_sheet(char, rest),
            "remove":  lambda: self._npc_remove(char, rest),
            "delete":  lambda: self._npc_remove(char, rest),
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler()
        else:
            self.msg(
                "Usage: npc list/create/load/set/tier/ambient/"
                "trigger/service/lore/sheet/remove\n"
                "Type 'help npc' for details."
            )

    # ------------------------------------------------------------------

    def _npc_list(self, char, here=False):
        from typeclasses.npc import NPC_TIER_LABELS
        from world.npc_loader import NPCLoader

        if here:
            room = char.location
            from typeclasses.npc import NPC
            npcs = [o for o in (room.contents if room else [])
                    if hasattr(o, 'db') and o.db.npc_tier is not None
                    and isinstance(o, NPC)]
            header = f"|wNPCs in {room.key if room else 'here'}:|n"
        else:
            npcs = NPCLoader.list_all_npcs()
            header = "|wAll NPCs:|n"

        if not npcs:
            self.msg(header + "\n  (none)")
            return

        lines = [header]
        for npc in npcs:
            tier  = npc.db.npc_tier or 1
            name  = npc.db.rp_name or npc.key
            loc   = npc.location.key if npc.location else "—"
            nid   = npc.db.npc_id or f"#{npc.id}"
            tlabel = NPC_TIER_LABELS.get(tier, f"T{tier}")
            lines.append(
                f"  |w{name}|n  |x{nid}  #{npc.id}|n  "
                f"{tlabel}  @ {loc}"
            )
        self.msg("\n".join(lines))

    def _npc_create(self, char, args):
        from evennia import create_object

        # Parse optional tier= suffix
        tier = 1
        name = args
        if " tier=" in args.lower():
            idx = args.lower().index(" tier=")
            try:
                tier = int(args[idx + 6:].strip())
            except ValueError:
                tier = 1
            name = args[:idx].strip()

        if not name:
            self.msg("Usage: npc create <name> [tier=N]")
            return

        tier = max(1, min(3, tier))

        npc = create_object(
            typeclass="typeclasses.npc.NPC",
            key=name,
            location=char.location,
        )
        npc.db.rp_name  = name
        npc.db.npc_tier = tier

        from typeclasses.npc import NPC_TIER_LABELS
        self.msg(
            f"|wNPC created:|n |w{name}|n (#{npc.id})  "
            f"{NPC_TIER_LABELS.get(tier, f'Tier {tier}')}\n"
            f"|xUse 'npc set {name} physical = <desc>' to describe them.|n"
        )

    def _npc_load(self, path):
        if not path:
            self.msg("Usage: npc load <yaml_file>")
            return

        from world.npc_loader import NPCLoader
        configs = NPCLoader.load_file(path)
        if not configs:
            self.msg(f"|rFailed to load '{path}' — see server logs for details.|n")
            return

        spawned = []
        for cfg in configs:
            npc = NPCLoader.spawn_from_config(cfg)
            if npc:
                spawned.append(npc.db.rp_name or npc.key)

        if spawned:
            self.msg(
                f"|wLoaded {len(spawned)} NPC(s) from {path}:|n\n"
                + "\n".join(f"  · {n}" for n in spawned)
            )
        else:
            self.msg(f"|rNo NPCs loaded from {path}.|n")

    def _npc_loadall(self, dir_path):
        from world.npc_loader import NPCLoader
        npcs = NPCLoader.spawn_all_from_directory(dir_path)
        if npcs:
            names = [n.db.rp_name or n.key for n in npcs]
            self.msg(
                f"|wLoaded {len(npcs)} NPC(s) from {dir_path}:|n\n"
                + "\n".join(f"  · {n}" for n in names)
            )
        else:
            self.msg(f"|rNo NPCs loaded from {dir_path}.|n")

    def _npc_set(self, char, args):
        # "npc set <name> <field> = <value>"
        if "=" not in args:
            self.msg(
                "Usage: npc set <npc> <field> = <value>\n"
                f"Fields: {', '.join(self.SET_FIELDS)}"
            )
            return

        left, _, value = args.partition("=")
        value = value.strip()
        left_parts = left.strip().split()

        if len(left_parts) < 2:
            self.msg(
                "Usage: npc set <npc> <field> = <value>\n"
                f"Fields: {', '.join(self.SET_FIELDS)}"
            )
            return

        # Last word on left side is the field, everything before is the npc name
        field    = left_parts[-1].lower()
        npc_name = " ".join(left_parts[:-1])

        if field not in self.SET_FIELDS:
            self.msg(
                f"Unknown field '{field}'.\n"
                f"Valid: {', '.join(self.SET_FIELDS)}"
            )
            return

        npc = _find_npc_in_room(char, npc_name) or _find_npc_global(npc_name)
        if not npc:
            self.msg(f"NPC '{npc_name}' not found.")
            return

        field_map = {
            "physical": "physical_desc",
            "outfit":   "outfit_desc",
            "mood":     "mood",
            "presence": "presence",
        }
        setattr(npc.db, field_map[field], value)
        npc_display = npc.db.rp_name or npc.key
        self.msg(
            f"|w{npc_display}|n {field} updated:\n"
            f"  {value[:80]}{'...' if len(value) > 80 else ''}"
        )

    def _npc_tier(self, char, args):
        parts = args.split()
        if len(parts) < 2:
            self.msg("Usage: npc tier <npc> <1-3>")
            return

        try:
            new_tier = int(parts[-1])
        except ValueError:
            self.msg("Tier must be 1, 2, or 3.")
            return

        npc_name = " ".join(parts[:-1])
        npc = _find_npc_in_room(char, npc_name) or _find_npc_global(npc_name)
        if not npc:
            self.msg(f"NPC '{npc_name}' not found.")
            return

        from typeclasses.npc import NPC_TIER_LABELS
        new_tier = max(1, min(3, new_tier))
        npc.db.npc_tier = new_tier
        self.msg(
            f"|w{npc.db.rp_name or npc.key}|n tier set to "
            f"{NPC_TIER_LABELS.get(new_tier, f'Tier {new_tier}')}."
        )

    def _npc_ambient(self, char, args):
        # "npc ambient <npc> add <line>" / "npc ambient <npc> list" / "npc ambient <npc> clear"
        parts = args.split(None, 2)
        if len(parts) < 2:
            self.msg(
                "Usage:\n"
                "  npc ambient <npc> add <line>\n"
                "  npc ambient <npc> list\n"
                "  npc ambient <npc> clear"
            )
            return

        # Find the subcmd — could be the 2nd word if npc name is one word,
        # or we need to detect "add/list/clear" anywhere in parts
        subcmds = ("add", "list", "clear")
        subcmd = None
        npc_name = None
        line_text = ""

        for i, word in enumerate(parts):
            if word.lower() in subcmds:
                subcmd = word.lower()
                npc_name = " ".join(parts[:i]).strip()
                line_text = parts[i + 1] if i + 1 < len(parts) else ""
                break

        if not subcmd or not npc_name:
            self.msg(
                "Usage: npc ambient <npc> add <line> | list | clear"
            )
            return

        npc = _find_npc_in_room(char, npc_name) or _find_npc_global(npc_name)
        if not npc:
            self.msg(f"NPC '{npc_name}' not found.")
            return

        npc_display = npc.db.rp_name or npc.key

        if subcmd == "add":
            if not line_text:
                self.msg("Provide the ambient line text.")
                return
            ambient = list(npc.db.ambient_base or [])
            ambient.append(line_text)
            npc.db.ambient_base = ambient
            self.msg(
                f"|w{npc_display}|n: ambient line added "
                f"({len(ambient)} total)."
            )

        elif subcmd == "list":
            ambient = list(npc.db.ambient_base or [])
            if not ambient:
                self.msg(f"|w{npc_display}|n has no ambient lines.")
                return
            lines = [f"|wAmbient lines for {npc_display}:|n"]
            for i, line in enumerate(ambient, 1):
                lines.append(f"  {i}. {line[:80]}")
            self.msg("\n".join(lines))

        elif subcmd == "clear":
            npc.db.ambient_base = []
            self.msg(f"|w{npc_display}|n: ambient lines cleared.")

    def _npc_trigger(self, char, args):
        # "npc trigger <npc> <keyword> = <response>"  or
        # "npc trigger <npc> <keyword>/clear"
        if not args:
            self.msg(
                "Usage:\n"
                "  npc trigger <npc> <keyword> = <response>\n"
                "  npc trigger <npc> <keyword>/clear"
            )
            return

        # Detect /clear switch
        clear = False
        if "/clear" in args.lower():
            args = args.lower().replace("/clear", "").strip()
            clear = True

        if "=" in args and not clear:
            left, _, response = args.partition("=")
            response = response.strip()
            parts = left.strip().split()
            if len(parts) < 2:
                self.msg("Usage: npc trigger <npc> <keyword> = <response>")
                return
            keyword  = parts[-1].lower()
            npc_name = " ".join(parts[:-1])
        else:
            parts = args.strip().split()
            if len(parts) < 2:
                self.msg("Usage: npc trigger <npc> <keyword>/clear")
                return
            keyword  = parts[-1].lower()
            npc_name = " ".join(parts[:-1])
            response = ""

        npc = _find_npc_in_room(char, npc_name) or _find_npc_global(npc_name)
        if not npc:
            self.msg(f"NPC '{npc_name}' not found.")
            return

        npc_display = npc.db.rp_name or npc.key
        triggers = dict(npc.db.triggers or {})

        if clear:
            if keyword not in triggers:
                self.msg(
                    f"|w{npc_display}|n has no trigger '{keyword}'."
                )
                return
            del triggers[keyword]
            npc.db.triggers = triggers
            self.msg(
                f"|w{npc_display}|n: trigger '{keyword}' removed."
            )
        else:
            if not response:
                self.msg("Provide a response text after '='.")
                return
            triggers[keyword] = {
                "type":       "say",
                "response":   response,
                "set_state":  {},
                "conditions": {},
            }
            npc.db.triggers = triggers
            self.msg(
                f"|w{npc_display}|n: trigger '{keyword}' "
                f"{'updated' if keyword in triggers else 'added'}."
            )

    def _npc_service(self, char, args):
        # "npc service <npc> <name> = <desc>"  or
        # "npc service <npc> <name>/clear"
        if not args:
            self.msg(
                "Usage:\n"
                "  npc service <npc> <name> = <desc>\n"
                "  npc service <npc> <name>/clear"
            )
            return

        clear = False
        if "/clear" in args.lower():
            args = args.lower().replace("/clear", "").strip()
            clear = True

        if "=" in args and not clear:
            left, _, desc = args.partition("=")
            desc  = desc.strip()
            parts = left.strip().split()
            if len(parts) < 2:
                self.msg("Usage: npc service <npc> <name> = <desc>")
                return
            svc_name = parts[-1].lower()
            npc_name = " ".join(parts[:-1])
        else:
            parts = args.strip().split()
            if len(parts) < 2:
                self.msg("Usage: npc service <npc> <name>/clear")
                return
            svc_name = parts[-1].lower()
            npc_name = " ".join(parts[:-1])
            desc = ""

        npc = _find_npc_in_room(char, npc_name) or _find_npc_global(npc_name)
        if not npc:
            self.msg(f"NPC '{npc_name}' not found.")
            return

        npc_display = npc.db.rp_name or npc.key
        services    = dict(npc.db.services or {})

        if clear:
            if svc_name not in services:
                self.msg(
                    f"|w{npc_display}|n has no service '{svc_name}'."
                )
                return
            del services[svc_name]
            npc.db.services = services
            self.msg(f"|w{npc_display}|n: service '{svc_name}' removed.")
        else:
            if not desc:
                self.msg("Provide a description after '='.")
                return
            services[svc_name] = {
                "desc":           desc,
                "consent_bypass": False,
                "bypass_reason":  "",
                "action":         "",
            }
            npc.db.services = services
            self.msg(
                f"|w{npc_display}|n: service '{svc_name}' saved."
            )

    def _npc_lore(self, char, args):
        # "npc lore <npc> <field name> = <value>"
        if "=" not in args:
            self.msg("Usage: npc lore <npc> <field name> = <value>")
            return

        left, _, value = args.partition("=")
        value = value.strip()
        parts = left.strip().split()

        if len(parts) < 2:
            self.msg("Usage: npc lore <npc> <field name> = <value>")
            return

        # Heuristic: look for NPC name first, then field name
        # We try matching from first word(s) against known NPCs
        npc = None
        field_name = None
        for split_at in range(1, len(parts)):
            candidate_npc  = " ".join(parts[:split_at])
            candidate_field = " ".join(parts[split_at:])
            npc_obj = _find_npc_in_room(char, candidate_npc) or _find_npc_global(candidate_npc)
            if npc_obj:
                npc = npc_obj
                field_name = candidate_field.strip()
                break

        if not npc or not field_name:
            self.msg(
                "Couldn't find the NPC. Make sure the name comes first.\n"
                "Usage: npc lore <npc> <field name> = <value>"
            )
            return

        npc_display = npc.db.rp_name or npc.key
        lore = list(npc.db.lore_fields or [])

        # Find existing field (case-insensitive)
        idx = next(
            (i for i, f in enumerate(lore)
             if f.get("name", "").lower() == field_name.lower()),
            None
        )

        if idx is not None:
            lore[idx]["value"] = value
            action = "updated"
        else:
            lore.append({"name": field_name, "value": value})
            action = "added"

        npc.db.lore_fields = lore
        self.msg(
            f"|w{npc_display}|n: lore field |w'{field_name}'|n {action}."
        )

    def _npc_sheet(self, char, args):
        if not args:
            self.msg("Usage: npc sheet <npc>")
            return
        npc = _find_npc_in_room(char, args) or _find_npc_global(args)
        if not npc:
            self.msg(f"NPC '{args}' not found.")
            return
        self.msg(npc.get_npc_sheet())

    def _npc_remove(self, char, args):
        if not args:
            self.msg("Usage: npc remove <npc>")
            return
        npc = _find_npc_in_room(char, args) or _find_npc_global(args)
        if not npc:
            self.msg(f"NPC '{args}' not found.")
            return
        npc_display = npc.db.rp_name or npc.key
        npc_id = npc.id
        npc.delete()
        self.msg(
            f"|w{npc_display}|n (#{npc_id}) has been removed permanently."
        )


# -----------------------------------------------------------------------
# Scene Extra commands
# -----------------------------------------------------------------------

class CmdExtra(MuxCommand):
    """
    Create and puppet a scene extra — a named temporary entity.

    Scene extras are player-created temporary characters that exist
    only during a scene. They have no stats or game data — just a
    name, an optional description, and the ability to speak and act
    through your commands.

    Usage:
        extra create <name> [= <desc>]    — create an extra here
        extra say <name> = <text>          — make them speak
        extra pose <name> = <text>         — make them act
        extra emote <name> = <text>        — same as pose
        extra whisper <name> = <text>      — quiet, italicised action
        extra remove <name>                — remove your extra
        extra list                         — list extras in room
        extras                             — same

    You can only puppet extras you created.
    Extras are cleared automatically when a scene ends.

    See also: npc, scene, freeform
    """
    key = "extra"
    aliases = ["extras"]
    locks = "cmd:all()"
    help_category = "Scene"

    def func(self):
        char = _char(self.caller)
        args = self.args.strip()

        # 'extras' alias with no args → list
        if self.cmdstring.lower() == "extras" and not args:
            self._extra_list(char)
            return

        if not args or args == "list":
            self._extra_list(char)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest   = parts[1].strip() if len(parts) > 1 else ""

        dispatch = {
            "create": lambda: self._extra_create(char, rest),
            "say":    lambda: self._extra_say(char, rest),
            "pose":   lambda: self._extra_pose(char, rest),
            "emote":  lambda: self._extra_pose(char, rest),
            "whisper":lambda: self._extra_whisper(char, rest),
            "remove": lambda: self._extra_remove(char, rest),
            "delete": lambda: self._extra_remove(char, rest),
            "list":   lambda: self._extra_list(char),
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler()
        else:
            self.msg(
                "Usage: extra create/say/pose/whisper/remove/list\n"
                "Type 'help extra' for details."
            )

    def _extra_list(self, char):
        room = char.location
        extras = _get_extras(room)
        if not extras:
            self.msg(
                "No scene extras here.\n"
                "Create one with: extra create <name> [= <desc>]"
            )
            return

        lines = ["|wScene extras here:|n\n"]
        for name, data in extras.items():
            desc = data.get("desc", "")
            pid  = data.get("puppet_by")
            puppet_note = ""
            if pid:
                from evennia import search_object
                puppeteer = search_object(f"#{pid}")
                if puppeteer:
                    pname = puppeteer[0].db.rp_name or puppeteer[0].key
                    puppet_note = f" |x(by {pname})|n"
            desc_note = f"  |x{desc[:60]}|n" if desc else ""
            lines.append(f"  |w{name}|n{puppet_note}{desc_note}")

        self.msg("\n".join(lines))

    def _extra_create(self, char, args):
        room = char.location
        if not room:
            self.msg("You must be in a room to create a scene extra.")
            return

        desc = ""
        name = args
        if "=" in args:
            name, _, desc = args.partition("=")
            name = name.strip()
            desc = desc.strip()

        if not name:
            self.msg("Usage: extra create <name> [= <desc>]")
            return

        extras = _get_extras(room)

        if name.lower() in {k.lower() for k in extras}:
            self.msg(
                f"There's already an extra named '{name}' here."
            )
            return

        extras[name] = {
            "desc":       desc,
            "puppet_by":  char.id,
            "created":    time.time(),
        }
        _save_extras(room, extras)

        char_name = char.db.rp_name or char.key
        desc_note = f'\n  |x"{desc}"|n' if desc else ""
        self.msg(
            f"Scene extra |w{name}|n created.{desc_note}\n"
            f"|xPuppet them with: extra say {name} = <text>|n"
        )

        # Notify room
        room.msg_contents(
            f"|x{name} drifts into the scene.|n",
            exclude=[self.caller]
        )

    def _check_puppet_permission(self, char, extra_data):
        """
        Check if char can puppet this extra.
        True if char created it or char is Builder+.
        """
        puppet_by = extra_data.get("puppet_by")
        if puppet_by and puppet_by == char.id:
            return True
        if char.check_permstring("Builder"):
            return True
        return False

    def _extra_say(self, char, args):
        if "=" not in args:
            self.msg("Usage: extra say <name> = <text>")
            return

        name_part, _, text = args.partition("=")
        extra_name = name_part.strip()
        text = text.strip()

        room = char.location
        canon_name, data = _find_extra(room, extra_name)

        if not canon_name:
            self.msg(f"No extra named '{extra_name}' here.")
            return
        if not self._check_puppet_permission(char, data):
            self.msg("You didn't create that extra.")
            return
        if not text:
            self.msg("What should they say?")
            return

        room.msg_contents(f'|w{canon_name}|n says, "|n{text}|n"')

    def _extra_pose(self, char, args):
        if "=" not in args:
            self.msg("Usage: extra pose <name> = <text>")
            return

        name_part, _, text = args.partition("=")
        extra_name = name_part.strip()
        text = text.strip()

        room = char.location
        canon_name, data = _find_extra(room, extra_name)

        if not canon_name:
            self.msg(f"No extra named '{extra_name}' here.")
            return
        if not self._check_puppet_permission(char, data):
            self.msg("You didn't create that extra.")
            return
        if not text:
            self.msg("What should they do?")
            return

        room.msg_contents(f"|w{canon_name}|n {text}")

    def _extra_whisper(self, char, args):
        if "=" not in args:
            self.msg("Usage: extra whisper <name> = <text>")
            return

        name_part, _, text = args.partition("=")
        extra_name = name_part.strip()
        text = text.strip()

        room = char.location
        canon_name, data = _find_extra(room, extra_name)

        if not canon_name:
            self.msg(f"No extra named '{extra_name}' here.")
            return
        if not self._check_puppet_permission(char, data):
            self.msg("You didn't create that extra.")
            return
        if not text:
            self.msg("What should they do?")
            return

        room.msg_contents(f"|x{canon_name} {text}|n")

    def _extra_remove(self, char, args):
        if not args:
            self.msg("Usage: extra remove <name>")
            return

        room = char.location
        canon_name, data = _find_extra(room, args)

        if not canon_name:
            self.msg(f"No extra named '{args}' here.")
            return
        if not self._check_puppet_permission(char, data):
            self.msg("You didn't create that extra.")
            return

        extras = _get_extras(room)
        del extras[canon_name]
        _save_extras(room, extras)

        self.msg(f"Scene extra |w{canon_name}|n removed.")
        room.msg_contents(
            f"|x{canon_name} fades from the scene.|n",
            exclude=[self.caller]
        )


# -----------------------------------------------------------------------
# Player NPC interaction commands
# -----------------------------------------------------------------------

class CmdGreet(MuxCommand):
    """
    Greet an NPC, triggering their greeting response.

    Usage:
        greet <npc>

    Fires the NPC's 'hello' or 'greet' trigger.
    If they have neither, they give a quiet nod.

    Only works on Tier 2+ (Scripted) NPCs.

    See also: ask, nservice
    """
    key = "greet"
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        char = _char(self.caller)
        args = self.args.strip()

        if not args:
            self.msg("Greet who? Usage: greet <npc>")
            return

        from typeclasses.npc import NPC, NPC_TIER_SCRIPTED
        npc = _find_npc_in_room(char, args)

        if not npc:
            self.msg(f"There's no one named '{args}' here to greet.")
            return

        if not isinstance(npc, NPC):
            self.msg(f"{npc.key} isn't an NPC.")
            return

        if npc.db.npc_tier < NPC_TIER_SCRIPTED:
            # Tier 1 — ambient only, acknowledge politely
            char_name = char.db.rp_name or char.key
            npc_name  = npc.db.rp_name or npc.key
            char.location.msg_contents(
                f"|w{char_name}|n greets |w{npc_name}|n, who continues about their day.",
            )
            return

        npc.trigger_greeting(char)


class CmdAsk(MuxCommand):
    """
    Ask an NPC about a topic, triggering their keyword response.

    Usage:
        ask <npc> about <keyword>

    Fires the NPC's trigger for that keyword.
    If no matching trigger exists, they give a quiet shrug.

    Only works on Tier 2+ (Scripted) NPCs.

    See also: greet, nservice
    """
    key = "ask"
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        char = _char(self.caller)
        args = self.args.strip()

        if not args:
            self.msg("Usage: ask <npc> about <keyword>")
            return

        from typeclasses.npc import NPC, NPC_TIER_SCRIPTED

        # Support both:
        #   ask witness about what you are
        #   ask witness what you are
        args_lower = args.lower()
        if " about " in args_lower:
            idx = args_lower.index(" about ")
            npc_name = args[:idx].strip()
            keyword  = args[idx + 7:].strip()
        else:
            # No "about" — try to match progressively longer NPC
            # names (first word, then two words, etc.) until one
            # resolves to an NPC in the room.
            words = args.split()
            npc_name = None
            keyword  = None
            for i in range(1, len(words)):
                candidate = " ".join(words[:i])
                rest      = " ".join(words[i:])
                if rest and _find_npc_in_room(char, candidate):
                    npc_name = candidate
                    keyword  = rest
                    break
            if not npc_name:
                self.msg("Usage: ask <npc> about <keyword>")
                return

        if not npc_name or not keyword:
            self.msg("Usage: ask <npc> about <keyword>")
            return

        npc = _find_npc_in_room(char, npc_name)

        if not npc:
            self.msg(f"There's no one named '{npc_name}' here.")
            return

        if not isinstance(npc, NPC):
            self.msg(f"You can't have a conversation with {npc.key}.")
            return

        if npc.db.npc_tier < NPC_TIER_SCRIPTED:
            self.msg(
                f"{npc.db.rp_name or npc.key} doesn't respond to questions."
            )
            return

        fired = npc.trigger_keyword(char, keyword)
        if not fired:
            npc_name_display = npc.db.rp_name or npc.key
            char.location.msg_contents(
                f"|w{npc_name_display}|n offers no clear answer "
                f"about |x{keyword}|n.",
            )


class CmdNService(MuxCommand):
    """
    List or request an NPC's available services.

    Usage:
        nservice <npc>              — list available services
        nservice <npc> <service>    — request a specific service

    Services are NPC-offered actions. Some NPCs offer services
    that can be used in scene regardless of your usual consent
    settings — this is intentional for quest and event content.

    Only works on Tier 2+ (Scripted) NPCs.

    See also: greet, ask
    """
    key = "nservice"
    aliases = ["nserv"]
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        char = _char(self.caller)
        args = self.args.strip()

        if not args:
            self.msg("Usage: nservice <npc> [service name]")
            return

        from typeclasses.npc import NPC, NPC_TIER_SCRIPTED

        # Try to split into "npc_name [service_name]"
        # We'll try matching progressively longer prefixes as the NPC name
        parts = args.split()
        npc = None
        service_name = ""

        for split_at in range(len(parts), 0, -1):
            candidate_npc  = " ".join(parts[:split_at])
            npc_obj = _find_npc_in_room(char, candidate_npc)
            if npc_obj and isinstance(npc_obj, NPC):
                npc = npc_obj
                service_name = " ".join(parts[split_at:]).strip()
                break

        if not npc:
            self.msg(f"No NPC named '{args.split()[0]}' here.")
            return

        npc_display = npc.db.rp_name or npc.key

        if npc.db.npc_tier < NPC_TIER_SCRIPTED:
            self.msg(f"|w{npc_display}|n doesn't offer any services.")
            return

        if not service_name:
            # List services
            services = npc.list_services()
            if not services:
                self.msg(f"|w{npc_display}|n has no services available.")
                return
            lines = [f"|wServices from {npc_display}:|n\n"]
            for sname, svc in services:
                desc = svc.get("desc", "")
                bypass = " |r[always available]|n" if svc.get("consent_bypass") else ""
                lines.append(f"  |w{sname}|n{bypass}: {desc}")
            lines.append(
                f"\n|xRequest with: nservice {npc_display} <service>|n"
            )
            self.msg("\n".join(lines))
        else:
            # Perform service
            success, msg = npc.perform_service(char, service_name)
            if not success:
                self.msg(f"|w{npc_display}|n: {msg}")


# -----------------------------------------------------------------------
# Scene extra cleanup utility (called from FreeformManager.end_scene)
# -----------------------------------------------------------------------

def clear_scene_extras(room):
    """
    Remove all scene extras from a room.
    Called by FreeformManager.end_scene() when a scene ends.

    Args:
        room: The room whose scene extras should be cleared.
    """
    extras = _get_extras(room)
    if not extras:
        return

    count = len(extras)
    names = list(extras.keys())
    _save_extras(room, {})

    if count:
        names_str = ", ".join(names[:5])
        if count > 5:
            names_str += f" and {count - 5} more"
        room.msg_contents(
            f"|x[Scene extras cleared: {names_str}]|n"
        )


# -----------------------------------------------------------------------
# Command lists for registration
# -----------------------------------------------------------------------

ALL_NPC_BUILDER_CMDS = [
    CmdNPC,
]

ALL_NPC_PLAYER_CMDS = [
    CmdExtra,
    CmdGreet,
    CmdAsk,
    CmdNService,
]
