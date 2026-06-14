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
    if laced:
        try:
            from typeclasses.bethany_script import bethany_deposit_effect
            bethany_deposit_effect(passenger, devotion=float(devotion))
        except Exception:
            pass
    return st


def eject(passenger):
    """Unbirth / free the passenger unconditionally. The §0 hook — always works, any nesting."""
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
