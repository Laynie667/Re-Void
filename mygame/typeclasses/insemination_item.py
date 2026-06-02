"""
typeclasses/insemination_item.py

InseminationAttachment — installs in an orifice or both-type zone on a machine
or character, depositing fluid into that zone per tick or on demand.

Source modes:
  "machine"  — infinite internal supply (no bank draw required)
  "bank"     — draws from the operator's GlobalFluidBank balance of fluid_type
  "random"   — draws from a random other player's bank balance of fluid_type
               (minimum MIN_RANDOM_DRAW_ML to avoid depleting tiny amounts)

Zone mechanics entry written on install:
  mechanics["insemination"] = {
      "source":          str    — 'machine' / 'bank' / 'random'
      "fluid_type":      str    — 'semen', 'milk', or any string
      "volume_per_tick": float  — ml deposited per trigger
      "ttl_hours":       float  — TTL of internal freeform deposit
      "item_dbref":      str    — this item's dbref
  }

Used by: CycleScript, machine-insemination trigger, and the manual
deposit pathway once an insemination attachment is installed.
"""

from typeclasses.mechanic_item import MechanicItem


MIN_RANDOM_DRAW_ML = 30.0   # don't touch bank balances below this


class InseminationAttachment(MechanicItem):
    """Installs fluid-delivery (insemination) into a zone."""

    mechanic_key = "insemination"

    def at_object_creation(self):
        super().at_object_creation()
        self.key = "Insemination Attachment"
        self.db.source          = "machine"   # machine / bank / random
        self.db.fluid_type      = "semen"
        self.db.volume_per_tick = 50.0
        self.db.ttl_hours       = 12.0

    def install_into_zone(self, room, zone_name: str, installer) -> tuple:
        zones = getattr(room.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"No zone '{zone_name}' found."

        zone_type = (zones[zone_name] or {}).get("zone_type", "")
        if zone_type not in ("orifice", "both"):
            return False, (
                f"Insemination can only be installed on orifice or "
                f"both-type zones ('{zone_name}' is '{zone_type}')."
            )

        zone = dict(zones[zone_name])
        mech = dict(zone.get("mechanics", {}) or {})

        if "insemination" in mech:
            return False, f"An insemination attachment is already on '{zone_name}'."

        mech["insemination"] = {
            "source":          self.db.source          or "machine",
            "fluid_type":      self.db.fluid_type      or "semen",
            "volume_per_tick": self.db.volume_per_tick or 50.0,
            "ttl_hours":       self.db.ttl_hours       or 12.0,
            "item_dbref":      self.dbref,
        }

        zone["mechanics"] = mech
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        room.db.zones = zones_copy

        return True, (
            f"Insemination attachment installed on '{zone_name}'.\n"
            f"  Source: {self.db.source}  |  Fluid: {self.db.fluid_type}  |  "
            f"Volume: {self.db.volume_per_tick:.0f}ml/tick  |  TTL: {self.db.ttl_hours:.0f}h"
        )


# ---------------------------------------------------------------------------
# Runtime deposit — called by CycleScript and other triggers
# ---------------------------------------------------------------------------

def do_inseminate(operator, target, zone_name: str, config: dict) -> str | None:
    """
    Execute one insemination deposit.

    operator — the character running the machine (or None for autonomous)
    target   — the character being inseminated
    zone_name — their orifice zone
    config   — the mechanics["insemination"] dict

    Returns the room-broadcast message string, or None if nothing happened.
    """
    import time
    from world.freeform_manager import FreeformManager
    from typeclasses.production_item import format_volume

    source     = config.get("source", "machine")
    fluid_type = config.get("fluid_type", "semen")
    volume     = config.get("volume_per_tick", 50.0) or 50.0
    ttl        = config.get("ttl_hours", 12.0) or 12.0

    actor_name  = (operator.db.rp_name or operator.name) if operator else "the machine"
    target_name = target.db.rp_name or target.name

    # Resolve fluid source
    if source == "bank" and operator:
        _draw_from_bank(operator, fluid_type, volume)
    elif source == "random":
        _draw_random(fluid_type, volume)
    # source == "machine" needs no draw

    # Create internal freeform deposit on target's zone
    item_key  = f"{fluid_type}_deposit_insem"
    item_desc = (
        f"A deposit of {fluid_type} from {actor_name} "
        f"({format_volume(volume)})."
    )

    zones = getattr(target.db, "zones", None) or {}
    if zone_name in zones:
        ok, _ = FreeformManager.place_item(
            target, zone_name, item_key, item_desc,
            operator.id if operator else 0,
            display_mode="in"
        )
        if ok:
            items = target.db.freeform_items or {}
            entry = items.get(item_key)
            if entry:
                entry["ttl_hours"]  = ttl
                entry["created_at"] = time.time()
                target.db.freeform_items = items

    # Notify WombRoom if one is installed on this zone
    try:
        from typeclasses.womb_room import add_fluid_from_zone
        add_fluid_from_zone(target, zone_name, volume, fluid_type)
    except Exception:
        pass

    zone_disp = zone_name.replace("_", " ")
    from world.milking_loader import pick_insemination_message
    msg = pick_insemination_message(source) or "The machine inseminates {target}'s {zone} with {fluid} ({volume})."
    return (
        msg.replace("{actor}", actor_name)
           .replace("{target}", target_name)
           .replace("{zone}", zone_disp)
           .replace("{fluid}", fluid_type)
           .replace("{volume}", format_volume(volume))
    )


def _draw_from_bank(char, fluid_type: str, amount: float):
    """Draw from operator's bank balance. Silent if insufficient."""
    try:
        from typeclasses.fluid_bank import GlobalFluidBank
        bank = GlobalFluidBank.get()
        char_id = str(char.id)
        records = dict(bank.db.records or {})
        rec = records.get(char_id, {})
        pending = rec.get("deposit_ml", 0.0) or 0.0
        if pending >= amount:
            rec["deposit_ml"] = max(0.0, pending - amount)
            records[char_id] = rec
            bank.db.records = records
    except Exception:
        pass


def _draw_random(fluid_type: str, amount: float):
    """Draw from a random contributor's bank balance. Silent if none found."""
    try:
        import random
        from typeclasses.fluid_bank import GlobalFluidBank
        bank = GlobalFluidBank.get()
        records = dict(bank.db.records or {})
        eligible = [
            (char_id, rec) for char_id, rec in records.items()
            if rec.get("fluid_type") == fluid_type
            and (rec.get("deposit_ml") or 0.0) >= MIN_RANDOM_DRAW_ML
        ]
        if not eligible:
            return
        char_id, rec = random.choice(eligible)
        rec = dict(rec)
        rec["deposit_ml"] = max(0.0, (rec.get("deposit_ml") or 0.0) - amount)
        records[char_id] = rec
        bank.db.records = records
    except Exception:
        pass
