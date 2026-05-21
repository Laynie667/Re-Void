"""
world/npc_loader.py

YAML-driven NPC loader for Re:Void.

Loads NPC definitions from YAML files and spawns, updates,
or despawns NPC objects in the world.

YAML FORMAT
-----------
Save .yaml files to world/npcs/<area>.yaml.

    npcs:
      - id: "forming_guide"              # unique id for lookup
        name: "The Forming Guide"
        tier: 2                          # 1=ambient 2=scripted 3=interactive
        location: "#1234"               # room dbref or object search string

        desc:
          physical: "A tall figure draped in pale silk..."
          outfit:   "..."
          mood:     "serene, unhurried"
          presence: "A quiet pull toward stillness."

        ambient:
          base:
            - "The guide turns a page in a small book."
            - "The guide's gaze drifts toward the far wall."
          states:
            recently_arrived:
              condition:
                room_state.new_arrivals: true
              lines:
                - "The guide glances toward {name} briefly."
          interval: [180, 360]          # optional min/max seconds

        triggers:
          hello:
            type: say
            response: "The guide inclines their head. 'Welcome.'"
            set_state:
              greeted: true
          help:
            type: say
            response:
              - "The guide gestures toward the archway."
              - "The guide tilts their head. 'What do you seek?'"
            conditions:
              greeted: true

        services:
          guidance:
            desc: "Offers a quiet word of direction."
            consent_bypass: false
            action: "places a hand briefly on {caller}'s shoulder."

        lore_fields:
          - name: "Role"
            value: "Threshold guardian"
          - name: "Affiliation"
            value: "The Forming"

        interaction_flags:
          mature: false
          consent_bypass: false

USAGE
-----
    from world.npc_loader import NPCLoader

    # Load a single file
    configs = NPCLoader.load_file("world/npcs/forming.yaml")
    for cfg in configs:
        NPCLoader.spawn_from_config(cfg)

    # Or load an entire directory
    NPCLoader.spawn_all_from_directory("world/npcs")

    # Find a spawned NPC by config id
    npc = NPCLoader.get_npc_by_id("forming_guide")

    # Update a live NPC from a new config dict
    NPCLoader.apply_config(npc, new_config)

    # Remove an NPC by id
    NPCLoader.despawn_npc("forming_guide")
"""

import os

from evennia import search_object, create_object
from evennia.utils import logger


NPC_TYPECLASS   = "typeclasses.npc.NPC"
NPC_TAG_CATEGORY = "npc_id"


class NPCLoader:
    """
    Static helper class for loading and managing YAML-defined NPCs.
    All methods are static — no instantiation needed.
    """

    @staticmethod
    def load_file(path):
        """
        Load NPC definitions from a YAML file.

        Args:
            path (str): Path to the .yaml file.

        Returns:
            list: List of NPC config dicts. Empty list on failure.
        """
        try:
            import yaml
        except ImportError:
            logger.log_err(
                "NPCLoader: PyYAML not installed. "
                "Run: pip install pyyaml --break-system-packages"
            )
            return []

        if not os.path.exists(path):
            logger.log_err(f"NPCLoader: file not found: {path}")
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            logger.log_err(f"NPCLoader: failed to parse {path}: {e}")
            return []

        if not data or not isinstance(data, dict):
            logger.log_err(f"NPCLoader: empty or invalid file: {path}")
            return []

        return data.get("npcs", []) or []

    @staticmethod
    def load_directory(dir_path):
        """
        Load all .yaml / .yml files in a directory.

        Args:
            dir_path (str): Path to the directory.

        Returns:
            list: Combined list of NPC config dicts from all files.
        """
        configs = []
        if not os.path.isdir(dir_path):
            logger.log_err(f"NPCLoader: directory not found: {dir_path}")
            return configs

        for fname in sorted(os.listdir(dir_path)):
            if fname.lower().endswith((".yaml", ".yml")):
                fpath = os.path.join(dir_path, fname)
                file_configs = NPCLoader.load_file(fpath)
                configs.extend(file_configs)
                logger.log_info(
                    f"NPCLoader: loaded {len(file_configs)} NPC(s) "
                    f"from {fname}"
                )

        return configs

    @staticmethod
    def spawn_from_config(config):
        """
        Spawn a single NPC from a config dict.

        If an NPC with the same id tag already exists, updates it in place.
        If no id is specified, always creates a new NPC.

        Args:
            config (dict): NPC config dict (from YAML).

        Returns:
            NPC object, or None on failure.
        """
        npc_id  = (config.get("id") or "").strip()
        name    = config.get("name", npc_id or "NPC").strip()
        loc_str = (config.get("location") or "").strip()

        # Resolve location
        location = None
        if loc_str:
            results = search_object(loc_str)
            if results:
                location = results[0]
            else:
                logger.log_err(
                    f"NPCLoader: location not found: '{loc_str}' "
                    f"for NPC '{npc_id or name}'"
                )

        # Look for existing NPC with this id tag
        npc = None
        if npc_id:
            tagged = NPCLoader.get_npc_by_id(npc_id)
            if tagged:
                npc = tagged
                logger.log_info(
                    f"NPCLoader: updating existing NPC "
                    f"'{npc_id}' (#{npc.id})"
                )

        # Create if not found
        if npc is None:
            try:
                npc = create_object(
                    typeclass=NPC_TYPECLASS,
                    key=name,
                    location=location,
                )
            except Exception as e:
                logger.log_err(
                    f"NPCLoader: failed to create NPC '{name}': {e}"
                )
                return None

            if npc_id:
                npc.tags.add(npc_id, category=NPC_TAG_CATEGORY)
                npc.db.npc_id = npc_id

            logger.log_info(
                f"NPCLoader: spawned NPC '{name}' (#{npc.id})"
                + (f" at {loc_str}" if loc_str else "")
            )
        else:
            # Update name and location if changed
            if npc.key != name:
                npc.key = name
            if location and npc.location != location:
                npc.move_to(location, quiet=True)

        # Apply the full config
        NPCLoader.apply_config(npc, config)
        return npc

    @staticmethod
    def apply_config(npc, config):
        """
        Apply a config dict to an existing NPC object.
        Only sets what the config specifies — won't clear unmentioned fields.

        Args:
            npc:    An NPC object.
            config: Config dict (from YAML or builder command).
        """
        from typeclasses.npc import (
            NPC_TIER_AMBIENT, NPC_TIER_SCRIPTED, NPC_TIER_INTERACTIVE
        )

        tier_map = {
            1: NPC_TIER_AMBIENT,
            2: NPC_TIER_SCRIPTED,
            3: NPC_TIER_INTERACTIVE,
        }

        # Tier
        raw_tier = config.get("tier", None)
        if raw_tier is not None:
            npc.db.npc_tier = tier_map.get(int(raw_tier), NPC_TIER_AMBIENT)

        # Name
        name = (config.get("name") or "").strip()
        if name:
            npc.db.rp_name = name
            npc.key = name

        # Description block
        desc = config.get("desc")
        if isinstance(desc, dict):
            if "physical" in desc:
                npc.db.physical_desc = desc["physical"]
            if "outfit" in desc:
                npc.db.outfit_desc = desc["outfit"]
            if "mood" in desc:
                npc.db.mood = desc["mood"]
            if "presence" in desc:
                npc.db.presence = desc["presence"]

        # Ambient block
        ambient = config.get("ambient")
        if ambient is not None:
            if isinstance(ambient, list):
                # Short form: ambient: ["line1", "line2"]
                npc.db.ambient_base = list(ambient)
            elif isinstance(ambient, dict):
                base = ambient.get("base")
                if base is not None:
                    npc.db.ambient_base = list(base)
                states = ambient.get("states")
                if states is not None:
                    npc.db.ambient_states = dict(states)
                interval = ambient.get("interval")
                if interval and len(interval) == 2:
                    npc.db.ambient_interval = list(interval)

        # Triggers
        triggers = config.get("triggers")
        if triggers is not None:
            # Normalise — ensure response is always present
            clean = {}
            for kw, tdata in triggers.items():
                clean[kw.lower()] = {
                    "type":       tdata.get("type", "say"),
                    "response":   tdata.get("response", ""),
                    "set_state":  tdata.get("set_state", {}),
                    "conditions": tdata.get("conditions", {}),
                }
            npc.db.triggers = clean

        # Services
        services_raw = config.get("services")
        if services_raw is not None:
            services = {}
            for sname, sdata in services_raw.items():
                services[sname.lower()] = {
                    "desc":           sdata.get("desc", ""),
                    "consent_bypass": bool(sdata.get("consent_bypass", False)),
                    "bypass_reason":  sdata.get("bypass_reason", ""),
                    "action":         sdata.get("action", ""),
                }
            npc.db.services = services

        # Lore fields
        lore = config.get("lore_fields")
        if lore is not None:
            npc.db.lore_fields = [
                {
                    "name":  f.get("name", ""),
                    "value": f.get("value", ""),
                }
                for f in lore
                if f.get("name")
            ]

        # Interaction flags
        iflags = config.get("interaction_flags")
        if iflags is not None:
            current = dict(npc.db.interaction_flags or {})
            current.update(iflags)
            npc.db.interaction_flags = current

        # Parrot mechanic
        if "react_to_say" in config:
            npc.db.react_to_say = bool(config["react_to_say"])
        parrot = config.get("parrot_responses")
        if parrot is not None:
            npc.db.parrot_responses = list(parrot)

        # Zones (optional — NPC zone descriptors for examine/zone-targeting)
        zones_raw = config.get("zones")
        if zones_raw is not None:
            zones = {}
            for zname, zdata in zones_raw.items():
                zones[zname] = {
                    "nude":             zdata.get("nude", ""),
                    "interior":         zdata.get("interior", ""),
                    "covered_by":       None,
                    "contents":         [],
                    "ambient":          [],
                    "zone_type":        zdata.get("zone_type", "surface"),
                    "intimate":         bool(zdata.get("intimate", False)),
                    "visibility":       zdata.get("visibility", "look"),
                    "consent_required": zdata.get("consent_required", "casual"),
                    "default":          True,
                    "parent":           zdata.get("parent", None),
                }
            npc.db.zones = zones

        # Store raw config for reference
        npc.db.npc_config = config

    @staticmethod
    def spawn_all_from_directory(dir_path="world/npcs"):
        """
        Load all YAML files from dir_path and spawn each NPC.

        Args:
            dir_path (str): Path to NPC yaml directory.

        Returns:
            list: All spawned/updated NPC objects.
        """
        configs = NPCLoader.load_directory(dir_path)
        npcs = []
        for cfg in configs:
            npc = NPCLoader.spawn_from_config(cfg)
            if npc:
                npcs.append(npc)
        logger.log_info(
            f"NPCLoader: finished — {len(npcs)} NPC(s) loaded."
        )
        return npcs

    @staticmethod
    def get_npc_by_id(npc_id):
        """
        Find a loaded NPC by its config id tag.

        Args:
            npc_id (str): The 'id' field from the YAML config.

        Returns:
            NPC object, or None if not found.
        """
        from evennia import search_tag
        results = search_tag(npc_id, category=NPC_TAG_CATEGORY)
        return results[0] if results else None

    @staticmethod
    def list_all_npcs():
        """
        Return all NPC objects currently in the world.

        Returns:
            list: All NPC objects.
        """
        from evennia.objects.manager import ObjectDB
        return list(
            ObjectDB.objects.filter(db_typeclass_path__endswith="npc.NPC")
        )

    @staticmethod
    def despawn_npc(npc_id):
        """
        Delete an NPC by config id.

        Args:
            npc_id (str): The 'id' field from the YAML config.

        Returns:
            bool: True if deleted, False if not found.
        """
        npc = NPCLoader.get_npc_by_id(npc_id)
        if not npc:
            return False
        npc_key = npc.key
        npc.delete()
        logger.log_info(f"NPCLoader: despawned '{npc_key}' ({npc_id})")
        return True
