"""
typeclasses/inflation_item.py

InflationItem — installs an inflation mechanic on an orifice or both-type zone.

The zone tracks volume_ml that can be increased via the inflate command or
the InflationAttachment on a machine, and drains passively each passive tick.

Zone mechanics entry written on install:
  zones[zone_name]['mechanics']['inflation'] = {
      'volume_ml':              float  — current accumulated volume
      'max_volume_ml':          float  — capacity (configurable)
      'drain_rate_ml_per_tick': float  — passive drain per 15-min tick
      'fluid_type':             str    — 'air' or any fluid string
      'item_dbref':             str    — this item's dbref
  }

Commands:
  inflate <target> [zone] [amount] [fluid]    — add volume
  inflate/self [zone] [amount] [fluid]        — self-inflate
  inflate/drain <target> [zone]               — remove all volume
  inflate/check <target> [zone]               — show current level

Threshold display in zone descs — use {inflation} token, which resolves to
one of these state strings based on % of max:
  "empty" (0%) / "slight" (<20%) / "notable" (<50%) / "full" (<90%) / "overfull" (>=90%)

Add per-state descriptions to zone's inflation_descs dict (see PROSE_NEEDED.txt).
"""

from typeclasses.mechanic_item import MechanicItem


INFLATION_THRESHOLDS = [
    (0.90, "overfull"),
    (0.50, "full"),
    (0.20, "notable"),
    (0.01, "slight"),
    (0.00, "empty"),
]


def get_inflation_state(volume_ml: float, max_volume_ml: float) -> str:
    """Return the threshold label for the current inflation level."""
    if max_volume_ml <= 0:
        return "empty"
    pct = volume_ml / max_volume_ml
    for threshold, label in INFLATION_THRESHOLDS:
        if pct >= threshold:
            return label
    return "empty"


def get_inflation_data(room_or_char, zone_name: str) -> dict | None:
    """Return the inflation mechanics dict for a zone, or None."""
    zones = getattr(room_or_char.db, "zones", None) or {}
    return (
        zones.get(zone_name, {})
             .get("mechanics", {}) or {}
    ).get("inflation")


def add_inflation_volume(room_or_char, zone_name: str,
                          amount: float, fluid_type: str = "air") -> tuple:
    """
    Add volume to a zone's inflation mechanic.
    Returns (new_volume, state_label) or (None, None) if zone has no inflation.
    """
    zones = getattr(room_or_char.db, "zones", None) or {}
    zone  = zones.get(zone_name, {})
    mech  = dict(zone.get("mechanics", {}) or {})
    inf   = dict(mech.get("inflation", {}))

    if not inf:
        return None, None

    inf["fluid_type"]  = fluid_type
    inf["volume_ml"]   = min(
        (inf.get("volume_ml", 0.0) or 0.0) + amount,
        inf.get("max_volume_ml", 500.0) or 500.0,
    )

    mech["inflation"] = inf
    zone_copy = dict(zone)
    zone_copy["mechanics"] = mech
    zones_copy = dict(zones)
    zones_copy[zone_name] = zone_copy
    room_or_char.db.zones = zones_copy

    state = get_inflation_state(inf["volume_ml"], inf.get("max_volume_ml", 500.0))

    # Notify WombRoom if one is installed on this zone
    try:
        from typeclasses.womb_room import add_fluid_from_zone
        add_fluid_from_zone(room_or_char, zone_name, amount,
                            inf.get("fluid_type", "fluid"))
    except Exception:
        pass

    return inf["volume_ml"], state


def drain_inflation(room_or_char, zone_name: str) -> bool:
    """Set inflation volume to 0. Returns True if zone had inflation."""
    zones = getattr(room_or_char.db, "zones", None) or {}
    zone  = zones.get(zone_name, {})
    mech  = dict(zone.get("mechanics", {}) or {})
    inf   = mech.get("inflation")
    if not inf:
        return False

    inf = dict(inf)
    inf["volume_ml"] = 0.0
    mech["inflation"] = inf
    zone_copy = dict(zone)
    zone_copy["mechanics"] = mech
    zones_copy = dict(zones)
    zones_copy[zone_name] = zone_copy
    room_or_char.db.zones = zones_copy
    return True


def tick_drain(room_or_char, zone_name: str):
    """Called every passive tick to drain inflation volume."""
    zones = getattr(room_or_char.db, "zones", None) or {}
    zone  = zones.get(zone_name, {})
    mech  = dict(zone.get("mechanics", {}) or {})
    inf   = mech.get("inflation")
    if not inf:
        return
    inf   = dict(inf)
    rate  = inf.get("drain_rate_ml_per_tick", 50.0) or 50.0
    vol   = (inf.get("volume_ml", 0.0) or 0.0) - rate
    inf["volume_ml"] = max(0.0, vol)
    mech["inflation"] = inf
    zone_copy = dict(zone)
    zone_copy["mechanics"] = mech
    zones_copy = dict(zones)
    zones_copy[zone_name] = zone_copy
    room_or_char.db.zones = zones_copy


# ---------------------------------------------------------------------------
# InflationItem
# ---------------------------------------------------------------------------

class InflationItem(MechanicItem):
    """
    Installs an inflation mechanic on an orifice or both-type zone.
    Install: use <InflationItem> on <zone>
    """

    mechanic_key = "inflation"

    def at_object_creation(self):
        super().at_object_creation()
        self.key = "Inflation Kit"
        self.db.max_volume_ml          = 500.0
        self.db.drain_rate_ml_per_tick = 50.0   # ml per 15-min passive tick

    def install_into_zone(self, room, zone_name: str, installer) -> tuple:
        zones = getattr(room.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"No zone '{zone_name}' found."

        # Typed-zone validation (shared validator; world/zone_types.py). Strict —
        # behaviour preserved (orifice or legacy 'both' only), centralised.
        from world.zone_types import accepts, zone_type_of
        if not accepts(zones[zone_name] or {}, "inflation"):
            return False, (f"Inflation can only be installed on orifice or both-type zones "
                           f"('{zone_name}' is '{zone_type_of(zones[zone_name] or {})}').")

        zone  = dict(zones[zone_name])
        mech  = dict(zone.get("mechanics", {}) or {})

        if "inflation" in mech:
            return False, f"Inflation is already installed on '{zone_name}'."

        mech["inflation"] = {
            "volume_ml":              0.0,
            "max_volume_ml":          self.db.max_volume_ml or 500.0,
            "drain_rate_ml_per_tick": self.db.drain_rate_ml_per_tick or 50.0,
            "fluid_type":             "air",
            "item_dbref":             self.dbref,
        }

        zone["mechanics"] = mech
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        room.db.zones = zones_copy

        return True, (
            f"Inflation mechanic installed on '{zone_name}'.\n"
            f"  Use |winflate <target> [zone] [amount] [fluid]|n to inflate.\n"
            f"  Use |winflate/drain <target> [zone]|n to drain.\n"
            f"  Use {{inflation}} token in zone descs for dynamic state display."
        )
