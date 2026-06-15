"""
world/passenger.py — the nested-passenger system: being carried INSIDE a host, and being
moved/covered between hosts by sex acts. The mechanical core behind unbirthing + the
Seraphine↔Bethany transfer (see design/seraphine_bethany.md).

Pure, dependency-light logic (testable without Evennia): a passenger's state lives in
`passenger.db.passenger` = {host, interior, covered, cover_fluid}. The optional physical
Evennia room-move (relocating the passenger's .location into a host's WombRoom interior) is
layered on top defensively by the scene/WombRoom code — this module just owns the state +
the transfer/cover rules + the §0 eject.

RULES (the user's scenarios, ruled in the design doc):
  * passenger in Host-A's BALLS + A inseminates Host-B  -> transfer the passenger into B's womb.
  * passenger in Host-A's WOMB  + Host-B cums in A      -> cover the passenger (B's load reaches
    them THROUGH the host; the membrane protects nobody — only an immune host's WILL is spared).
  * Bethany's laced cum lands on the PASSENGER in full (cumflation + DEVOTION) regardless of host.

§0: eject() unbirths a passenger unconditionally; `passenger` is in FACILITY_FLAGS so
force_clear/escape clear it. escape()'s move_to-home already relocates the player out of any
host interior; eject keeps the state honest.
"""

INTERIORS = ("womb", "balls")


# ── physical layer (Evennia) ────────────────────────────────────────────────
# The state functions below own the RULES and are pure/testable. These helpers
# layer the REAL move on top: relocating the passenger's .location into the
# host's actual WombRoom interior, flooding it for real on cover, and moving the
# passenger back OUT on eject (the §0 belt-and-suspenders). Every helper is
# wrapped so that with no Evennia present they no-op cleanly and the rules layer
# behaves exactly as the unit tests expect.

def _resolve_host(host_name):
    """Find a host Character by rp_name or key (case-insensitive). None if absent."""
    if not host_name:
        return None
    try:
        from typeclasses.characters import Character
        want = str(host_name).lower()
        for ch in Character.objects.all():
            nm = (getattr(ch.db, "rp_name", None) or ch.key or "")
            if nm.lower() == want:
                return ch
    except Exception:
        return None
    return None


def _interior_room(host_char, kind="womb"):
    """The host's installed WombRoom matching `kind` ('womb'/'balls'); falls back to any
    interior the host has. None if the host has no interior installed."""
    if not host_char:
        return None
    try:
        from evennia import search_object
        zones = getattr(host_char.db, "zones", None) or {}
        candidates = []
        for _zname, zdata in zones.items():
            wr = ((zdata or {}).get("mechanics") or {}).get("womb_room")
            dbref = (wr or {}).get("room_dbref")
            if not dbref:
                continue
            res = search_object(dbref, exact=True)
            if not res:
                continue
            room = res[0]
            rtype = getattr(room.db, "room_type", "womb") or "womb"
            candidates.append((rtype, room))
        for rtype, room in candidates:
            if rtype == kind:
                return room
        return candidates[0][1] if candidates else None
    except Exception:
        return None


def _relocate(passenger, room):
    """Move the passenger physically into `room`. No-op without a real room/move_to."""
    try:
        if room is not None and getattr(passenger, "location", None) != room:
            passenger.move_to(room, quiet=True, move_hooks=False)
            return True
    except Exception:
        return False
    return False


def _exit_to_safe(passenger):
    """Move the passenger OUT of any host interior to a safe room (the host's location, or
    the passenger's home). Only acts if currently inside a WombRoom. The §0 physical exit."""
    try:
        from typeclasses.womb_room import WombRoom
        loc = getattr(passenger, "location", None)
        if not isinstance(loc, WombRoom):
            return False
        host = loc._get_host() if hasattr(loc, "_get_host") else None
        dest = (getattr(host, "location", None) if host else None) or getattr(passenger, "home", None)
        if dest is not None and dest != loc:
            passenger.move_to(dest, quiet=True, move_hooks=False)
            return True
    except Exception:
        return False
    return False


def _physical_board(passenger, host_name, interior):
    """Relocate the passenger into the host's interior room, if one exists."""
    try:
        _relocate(passenger, _interior_room(_resolve_host(host_name), interior))
    except Exception:
        pass


def status(passenger):
    """The passenger's current carry-state dict (empty if not a passenger). Read-only copy."""
    return dict(getattr(getattr(passenger, "db", None), "passenger", None) or {})


def is_passenger(passenger):
    return bool(status(passenger).get("host"))


def board(passenger, host_name, interior="womb"):
    """Take `passenger` INTO `host` (unbirth/insert). interior = 'womb' or 'balls'."""
    interior = interior if interior in INTERIORS else "womb"
    st = {"host": host_name, "interior": interior, "covered": False, "cover_fluid": None}
    passenger.db.passenger = st
    _physical_board(passenger, host_name, interior)
    return st


def transfer(passenger, to_host_name, to_interior="womb"):
    """Move a riding passenger from their current host into another (deposit-on-insemination).
    No-ops cleanly if they aren't a passenger. Returns the new state."""
    st = status(passenger)
    if not st.get("host"):
        return st
    st["host"] = to_host_name
    st["interior"] = to_interior if to_interior in INTERIORS else "womb"
    st["covered"] = False
    st["cover_fluid"] = None
    passenger.db.passenger = st
    _physical_board(passenger, st["host"], st["interior"])
    return st


def cover(passenger, fluid="semen", laced=True, devotion=6.0):
    """An external deposit floods the host's interior and reaches the passenger. The cover lands
    on the passenger in full; if laced, the DEVOTION takes them (the host's own immunity, if any,
    does NOT protect the passenger). Returns the new state."""
    st = status(passenger)
    if not st.get("host"):
        return st
    st["covered"] = True
    st["cover_fluid"] = fluid
    passenger.db.passenger = st
    # Flood the real interior room the passenger rides in, so the WombRoom reflects the deposit.
    try:
        room = _interior_room(_resolve_host(st["host"]), st.get("interior", "womb"))
        if room is not None and hasattr(room, "add_fluid"):
            room.add_fluid(4000.0, fluid)
    except Exception:
        pass
    if laced:
        try:
            from typeclasses.bethany_script import bethany_deposit_effect
            bethany_deposit_effect(passenger, devotion=float(devotion))
        except Exception:
            pass
    return st


def eject(passenger):
    """Unbirth / free the passenger unconditionally. The §0 hook — always works, any nesting.
    Moves the passenger physically OUT of any host interior, then clears the carry-state."""
    _exit_to_safe(passenger)
    try:
        passenger.db.passenger = None
    except Exception:
        pass
    return True


def carried_line(passenger):
    """A short descriptive clause of where/how the passenger is riding, for prose. '' if free."""
    st = status(passenger)
    host = st.get("host")
    if not host:
        return ""
    where = "womb" if st.get("interior") == "womb" else "balls"
    cov = ", flooded and covered" if st.get("covered") else ""
    return f"carried inside {host}'s {where}{cov}"


def provision_passenger_interior(host_char, kind="womb", zone=None):
    """Create + install a real WombRoom interior of `kind` ('womb'/'balls') on `host_char`'s
    orifice zone, so the physical carry layer has somewhere to put a passenger. Idempotent: if
    an interior of this kind already exists it returns it. Returns (room, "") or (None, reason).
    Evennia-only; safe to call from a build/scene. The zone defaults to a sensible name per kind."""
    kind = kind if kind in INTERIORS else "womb"
    try:
        from evennia import create_object
        from typeclasses.womb_room import WombRoom
    except Exception as e:
        return None, f"Evennia unavailable: {e}"
    # already installed?
    existing = _interior_room(host_char, kind)
    if existing is not None:
        return existing, ""
    zone = zone or ("womb" if kind == "womb" else "sack")
    zones = getattr(host_char.db, "zones", None) or {}
    if zone not in zones:
        return None, (f"No zone '{zone}' on the host to install a {kind} interior on — "
                      f"create an orifice zone there first.")
    name = f"Inside {(getattr(host_char.db, 'rp_name', None) or host_char.key)} ({kind})"
    try:
        room = create_object(WombRoom, key=name)
        room.db.room_type = kind
        ok, reason = room.install(host_char, zone)
        if not ok:
            room.delete()
            return None, reason
        return room, ""
    except Exception as e:
        return None, f"Could not provision interior: {e}"
