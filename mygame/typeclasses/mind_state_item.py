"""
typeclasses/mind_state_item.py

MindStateItem — a zone-install that lives on a character's "mind" zone and is the
single, visible, mechanically-backed home for everything the Facility does to her
head: conditioning, suggestibility, docility, drug dependence, the cravings it's
built into her, her designation, her grade, and the installed triggers anyone can
speak at her.

It is a real zone item (installed like a ProductionItem/WombRoom), tracked on
db.facility_items so the reset path tears it down. It does three jobs:

  1. RENDER — `look mind` / `study mind` show a live readout of her processing
     state, written cold and clinical. The mind made inspectable, like everything
     else here.
  2. DERIVE — it computes and stores `db.docility` (0-100) from conditioning +
     suggestibility + dependence, which the defiance system consults (see
     world.compliance.register_defiance): the more docile she is, the less her
     own resistance will land.
  3. DRIVE — `tick()` (called each cycle beat) applies the ongoing pull of what's
     been done to her: withdrawal from dependence, the ache of being empty from
     the cravings, a faint suggestibility-scaled conditioning drift — so those
     stats bite every phase, not only in a 'rest' beat the realm never runs.

OOC floor: nothing here gates the reset. force_clear/escape/purge strip the item,
the mind zone, and every stat it reads.
"""

import random
from evennia import DefaultObject

# Conditioning stage labels (mirrors world.conditioning._THRESHOLDS).
_COND_STAGES = [
    (0.0,   "baseline"),
    (20.0,  "softened"),
    (40.0,  "speech drifting"),
    (60.0,  "trigger-seated"),
    (80.0,  "designated"),
    (100.0, "name slipping"),
    (130.0, "doll-state"),
    (160.0, "identity dissolving"),
    (200.0, "self-locked"),
    (250.0, "imprinted livestock"),
]


def _stage(value):
    label = _COND_STAGES[0][1]
    for thresh, name in _COND_STAGES:
        if value >= thresh:
            label = name
    return label


def _bar(value, cap, width=20):
    """A little ASCII meter."""
    frac = max(0.0, min(1.0, (value or 0) / cap)) if cap else 0.0
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled)


def compute_docility(character):
    """Docility (0-100) derived from the real stats. Stored on db.docility so the
    defiance system can consult it. The deeper she's processed, the more docile."""
    cond = float(getattr(character.db, "conditioning", 0) or 0)
    sug  = float(getattr(character.db, "suggestibility", 0) or 0)
    dep  = float(getattr(character.db, "drug_dependence", 0) or 0)
    doc  = cond * 0.30 + sug * 1.5 + dep * 4.0
    if getattr(character.db, "cum_craving", False):
        doc += 6
    if getattr(character.db, "perpetual_heat", False):
        doc += 6
    doc = max(0.0, min(100.0, doc))
    character.db.docility = doc
    return doc


class MindStateItem(DefaultObject):
    """The processing read-out and mental driver, installed on the 'mind' zone."""

    def at_object_creation(self):
        self.key = "Facility Mind-State Monitor"
        self.db.desc = ("A read-out of a processed mind: what's been put in, what's been "
                        "taken out, and how much of her is left to argue.")
        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        self.db.is_installed = False

    # ------------------------------------------------------------------ install
    def install(self, character, zone_name="mind"):
        if self.db.installed_on_char:
            return False, f"{self.key} is already installed."
        zones = dict(getattr(character.db, "zones", None) or {})
        if zone_name not in zones:
            return False, f"No zone '{zone_name}'."
        zone = dict(zones[zone_name])
        mech = dict(zone.get("mechanics", {}) or {})
        if "mind_state" in mech:
            return False, "A mind-state monitor is already installed."
        mech["mind_state"] = {"item_dbref": self.dbref, "item_name": self.key}
        zone["mechanics"] = mech
        zones[zone_name] = zone
        character.db.zones = zones
        self.db.installed_on_char = character
        self.db.installed_on_zone = zone_name
        self.db.is_installed = True
        self.location = character
        self.refresh(character)
        return True, ""

    def uninstall(self):
        char = self.db.installed_on_char
        zone_name = self.db.installed_on_zone
        if char and zone_name:
            zones = dict(getattr(char.db, "zones", None) or {})
            if zone_name in zones:
                zone = dict(zones[zone_name])
                mech = dict(zone.get("mechanics", {}) or {})
                mech.pop("mind_state", None)
                zone["mechanics"] = mech
                zones[zone_name] = zone
                char.db.zones = zones
        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        self.db.is_installed = False
        return True, ""

    # ------------------------------------------------------------------ render
    def render(self, character=None):
        c = character or self.db.installed_on_char
        if not c:
            return self.db.desc or ""
        d = c.db
        cond = float(getattr(d, "conditioning", 0) or 0)
        sug  = float(getattr(d, "suggestibility", 0) or 0)
        doc  = compute_docility(c)
        dep  = int(getattr(d, "drug_dependence", 0) or 0)
        grade = getattr(d, "facility_grade", None) or "Unprocessed"
        desig = getattr(d, "designation", None)
        triggers = list(getattr(d, "installed_triggers", None) or [])
        filters  = list(getattr(d, "active_speech_filters", None) or [])

        lines = []
        lines.append("|wFACILITY MIND-STATE — subject read-out|n")
        lines.append(f"  |xGrade:|n {grade}" + (f"   |xDesignation:|n {desig}" if desig else ""))
        lines.append(f"  |xConditioning:|n {cond:5.1f}  |x[{_bar(cond, 250)}]|n  ({_stage(cond)})")
        lines.append(f"  |xSuggestibility:|n {sug:4.1f}  |x[{_bar(sug, 20)}]|n")
        lines.append(f"  |xDocility:|n {doc:5.1f}  |x[{_bar(doc, 100)}]|n")
        if dep:
            lines.append(f"  |xDrug dependence:|n {dep}  |x[{_bar(dep, 10)}]|n")
        cravings = []
        if getattr(d, "cum_craving", False):
            cravings.append("bred/filled (empty reads as wrong)")
        if getattr(d, "perpetual_heat", False):
            cravings.append("in permanent heat")
        if getattr(d, "lactation_locked", False):
            cravings.append("milk locked on")
        if cravings:
            lines.append("  |xConditioned cravings:|n " + "; ".join(cravings))
        if filters:
            lines.append("  |xSpeech overwrite:|n " + ", ".join(filters))
        if triggers:
            lines.append("  |xInstalled triggers|n (anyone may speak these at her):")
            for tr in sorted(triggers, key=lambda e: -int(e.get("strength", 1)))[:8]:
                ph = tr.get("phrase", "?")
                rs = tr.get("response", "?")
                st = int(tr.get("strength", 1))
                perm = " (permanent)" if tr.get("permanent") else ""
                lines.append(f"    |R\"{ph}\"|n → {rs} ×{st}{perm}")
        else:
            lines.append("  |xInstalled triggers:|n none yet.")

        # Ownership / devotion to Bethany, when present.
        dev = float(getattr(d, "bethany_devotion", 0) or 0)
        if getattr(d, "bethany_owned", False) or dev > 0 or getattr(d, "facility_owner", None):
            owner = getattr(d, "facility_owner", None) or "Bethany"
            lines.append(f"  |xOwner:|n {owner}   |xDevotion:|n {dev:4.1f}  |x[{_bar(dev, 100)}]|n")
            clauses = list(getattr(d, "bethany_clauses", None) or [])
            if clauses:
                lines.append("  |xPersonal clauses:|n " + ", ".join(clauses))

        # Lineage — her own offspring, and the get bred back into her (incest loop).
        counts = dict(getattr(d, "offspring_counts", None) or {})
        if counts:
            total = sum(int(v) for v in counts.values())
            by = ", ".join(f"{k}×{int(v)}" for k, v in counts.items())
            lines.append(f"  |xOffspring dropped:|n {total} ({by})")
            roster = list(getattr(d, "offspring_roster", None) or [])
            if roster:
                lines.append("    |xher own get are raised on her milk and bred back into "
                             "her — the bloodline folded through her body, generation on "
                             "generation.|n")

        # Trained body-state — what her holes can now take, and how ruined.
        try:
            from world.gang_breeding import animal_holes, hole_capabilities, gape_word
            parts = []
            for label, z in animal_holes(c).items():
                if not z:
                    continue
                caps = hole_capabilities(c, z)
                cap_s = ("/".join(sorted(caps))) if caps else "—"
                parts.append(f"{label} ({gape_word(c, z)}; takes: {cap_s})")
            if parts:
                lines.append("  |xHoles (trained):|n " + "; ".join(parts))
        except Exception:
            pass

        # What FORGET has taken out of her.
        forgotten = list(getattr(d, "facility_forgotten", None) or [])
        if forgotten:
            lines.append(f"  |xRedacted (FORGET):|n {len(forgotten)} item(s) removed —")
            for item in forgotten[-5:]:
                lines.append(f"    |x· {item}|n")

        return "\n".join(lines)

    def refresh(self, character=None):
        """Recompute docility and write the live read-out into the mind zone desc."""
        c = character or self.db.installed_on_char
        if not c:
            return
        zone_name = self.db.installed_on_zone or "mind"
        zones = dict(getattr(c.db, "zones", None) or {})
        if zone_name in zones:
            zone = dict(zones[zone_name])
            readout = self.render(c)
            # Character zones render their "nude" field on `look <her> mind`.
            zone["nude"] = readout
            zone["desc"] = readout   # harmless mirror for any desc-based path
            zones[zone_name] = zone
            c.db.zones = zones

    # ------------------------------------------------------------------- drive
    def tick(self, character=None):
        """Apply the ongoing pull of what's been done to her, every cycle beat."""
        c = character or self.db.installed_on_char
        if not c:
            return
        d = c.db
        # Faint suggestibility-scaled conditioning drift (the head keeps settling).
        sug = float(getattr(d, "suggestibility", 0) or 0)
        if sug > 0 and random.random() < 0.5:
            try:
                from world.conditioning import add_conditioning
                add_conditioning(c, 0.2 + sug * 0.02, source="mind")
            except Exception:
                pass
        # Withdrawal from dependence — the body claws for the next dose.
        dep = int(getattr(d, "drug_dependence", 0) or 0)
        if dep and random.random() < min(0.6, 0.15 + dep * 0.08):
            try:
                from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                ensure_arousal_script(c); add_arousal(c, 8.0 + dep * 2)
            except Exception:
                pass
            c.msg("|G  your skin crawls for the next dose — the craving louder than thought, "
                  "and you'd sign anything, take anything, to make it the next phase already.|n")
        # The conditioned ache of being empty.
        if getattr(d, "cum_craving", False) and random.random() < 0.4:
            try:
                from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                ensure_arousal_script(c); add_arousal(c, 10.0)
            except Exception:
                pass
            c.msg("|G  empty is unbearable now — you clench around nothing, hollow and wanting, "
                  "your own body begging to be filled back up.|n")
        self.refresh(c)


def find_mind_item(character):
    """Return the installed MindStateItem for a character, or None."""
    zones = getattr(character.db, "zones", None) or {}
    entry = ((zones.get("mind") or {}).get("mechanics") or {}).get("mind_state")
    if not entry:
        return None
    from evennia import search_object
    res = search_object(entry.get("item_dbref", ""), exact=True)
    if res and isinstance(res[0], MindStateItem):
        return res[0]
    return None


def refresh_mind(character):
    """Convenience: refresh the read-out if she has a monitor installed."""
    item = find_mind_item(character)
    if item:
        item.refresh(character)
    return item
