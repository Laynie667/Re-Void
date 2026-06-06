"""
typeclasses/fluid_bank.py

GlobalFluidBank — singleton persistent script attached to the server.

Serves as the intermediary between extraction events and in-world containers.
All fluid extraction (milking, climax, suck, handmilk) deposits here.
The bank accumulates partial volumes and creates standard-size bottles (591ml / 20 fl oz)
once enough has built up, then routes them to any FluidFridge in the game.

Access pattern:
    from typeclasses.fluid_bank import GlobalFluidBank
    bank = GlobalFluidBank.get()
    bank.deposit(char, ml=45.0, fluid_type="milk", fluid_flavor="warm honey")

Per-character bank records (db.records[str(char.id)]):
    {
        "lifetime_ml":   float,   # total ever produced, never decremented
        "deposit_ml":    float,   # partial bottle buffer (< BOTTLE_SIZE_ML)
        "fluid_type":    str,
        "fluid_flavor":  str or None,
    }
"""

from evennia import DefaultScript


BOTTLE_SIZE_ML = 591.0   # 20 fl oz — one standard bottle


class GlobalFluidBank(DefaultScript):
    """Singleton fluid accumulation and bottling service."""

    def at_script_creation(self):
        self.key        = "global_fluid_bank"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 1800   # 30-min fridge check (placeholder)
        self.db.records = {}

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get(cls):
        """
        Return the singleton bank, creating it if it doesn't exist.

        Uses evennia.search_script() — the proper Evennia-recommended way to
        find scripts by key — rather than raw ScriptDB queries.

        Usage:
            bank = GlobalFluidBank.get()
        """
        from evennia import search_script
        all_results = search_script("global_fluid_bank") or []
        results = [s for s in all_results if s.key == "global_fluid_bank"]
        if results:
            for result in results:
                if isinstance(result, cls):
                    return result
            return results[0]

        # Not found — create with key set at creation time (more reliable)
        from evennia.utils import create
        bank = create.create_script(
            cls,
            key="global_fluid_bank",
            persistent=True,
            autostart=True,
        )
        return bank

    # ------------------------------------------------------------------
    # Deposit
    # ------------------------------------------------------------------

    def deposit(self, char, ml: float, fluid_type: str,
                fluid_flavor: str | None = None) -> list:
        """
        Deposit extracted fluid.  Accumulates fractional amounts and creates
        591ml bottles once enough has built up.  Bottles are routed to any
        FluidFridge in the game automatically.

        Args:
            char:         The producing character.
            ml:           Volume in millilitres being deposited.
            fluid_type:   'milk', 'semen', 'urine', or custom string.
            fluid_flavor: Optional flavor description.

        Returns:
            List of FluidBottle objects created this call (may be empty if
            the deposit didn't yet reach a full bottle).
        """
        if ml <= 0:
            return []

        char_id = str(char.id)
        records = dict(self.db.records or {})

        if char_id not in records:
            records[char_id] = {
                "lifetime_ml":  0.0,
                "deposit_ml":   0.0,
                "fluid_type":   fluid_type,
                "fluid_flavor": fluid_flavor,
            }

        rec = records[char_id]
        rec["lifetime_ml"]  = (rec.get("lifetime_ml")  or 0.0) + ml
        rec["deposit_ml"]   = (rec.get("deposit_ml")   or 0.0) + ml
        # Always track the most recent flavor / type so bottles are labeled right
        rec["fluid_type"]   = fluid_type
        rec["fluid_flavor"] = fluid_flavor

        # ── Bottling loop ──────────────────────────────────────────────
        from typeclasses.fluid_bottle import FluidBottle
        from evennia.utils import create

        char_name = char.db.rp_name or char.name
        bottles   = []

        while rec["deposit_ml"] >= BOTTLE_SIZE_ML:
            rec["deposit_ml"] -= BOTTLE_SIZE_ML
            bottle = create.create_object(
                FluidBottle,
                key=f"bottle of {char_name}'s {fluid_type}",
                location=None,   # placed by _route_to_fridge
            )
            bottle.db.producer_name = char_name
            bottle.db.fluid_type    = fluid_type
            bottle.db.fluid_flavor  = fluid_flavor
            bottle.db.volume_ml     = BOTTLE_SIZE_ML
            bottles.append(bottle)

        records[char_id] = rec
        self.db.records  = records

        if bottles:
            self._route_to_fridge(bottles, char)

        return bottles

    # ------------------------------------------------------------------
    # Fridge routing
    # ------------------------------------------------------------------

    def _route_to_fridge(self, bottles: list, char=None):
        """Place completed bottles into a fridge. Priority: a fridge in the producer's
        own room → any fridge in the game → (last resort) the producer's room itself, so
        a bottle is never silently lost to limbo when no fridge exists."""
        from typeclasses.fluid_fridge import FluidFridge

        loc = getattr(char, "location", None) if char else None

        # 1) a fridge in the room where the fluid was produced (the one you're watching)
        fridge = None
        if loc:
            try:
                fridge = next((o for o in loc.contents
                               if o.is_typeclass(FluidFridge, exact=False)), None)
            except Exception:
                fridge = None

        # 2) otherwise the first fridge anywhere (subclass-tolerant path match)
        if not fridge:
            from evennia.objects.models import ObjectDB
            for obj in ObjectDB.objects.filter(
                    db_typeclass_path__icontains="fluid_fridge"):
                try:
                    cand = obj.typeclass
                    if cand.is_typeclass(FluidFridge, exact=False):
                        fridge = cand
                        break
                except Exception:
                    continue

        target = fridge or loc   # never drop to limbo if we can help it
        if not target:
            return
        for bottle in bottles:
            bottle.location = target

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def get_record(self, char) -> dict:
        """Return the bank record for a character (read-only copy)."""
        records = self.db.records or {}
        return dict(records.get(str(char.id), {
            "lifetime_ml":  0.0,
            "deposit_ml":   0.0,
            "fluid_type":   None,
            "fluid_flavor": None,
        }))

    def get_deposit_summary(self, char) -> str:
        """Human-readable summary for the fluid balance command."""
        from typeclasses.production_item import format_volume
        rec = self.get_record(char)
        lifetime = rec.get("lifetime_ml",  0.0)
        pending  = rec.get("deposit_ml",   0.0)
        needed   = BOTTLE_SIZE_ML - pending
        return (
            f"|wFluid Bank — {char.db.rp_name or char.name}|n\n"
            f"  Lifetime produced:  {format_volume(lifetime)}\n"
            f"  Pending (unbottled): {format_volume(pending)}"
            + (f" ({format_volume(needed)} until next bottle)" if pending > 0 else "")
        )
