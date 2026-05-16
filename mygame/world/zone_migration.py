"""
Re:Void — Zone Hierarchy Migration
====================================
Migrates all character zone dicts from the old flat structure to the new
hierarchical structure introduced with the DEFAULT_ZONE_TREE rewrite.

Run once via:
    evennia run world/zone_migration.py

Or from the in-game superuser console:
    @py from world.zone_migration import run; run()

What this script does
---------------------
1.  Adds "parent" and "interior" keys to every existing zone that is
    missing them.
2.  Sets the correct parent for every old flat zone (e.g. hair → head).
3.  Creates new root zones that didn't exist before:
        head, torso, groin
4.  Promotes existing zones that are now roots (neck, arms, legs) by
    setting their parent to None.
5.  Creates new leaf zones that didn't exist before:
        mouth (child of face), tongue (child of mouth)
6.  Is **idempotent** — safe to run multiple times.  Zones that already
    have correct values are left unchanged.

Zones NOT touched by this migration
-------------------------------------
* Any zone whose name is not in the known old or new zone list is left
  completely alone (freeform player-created zones).  Only their "parent"
  and "interior" keys are backfilled if missing.
"""

from evennia.objects.models import ObjectDB
from django.conf import settings

# ---------------------------------------------------------------------------
# Canonical parent mapping for the new hierarchy
# ---------------------------------------------------------------------------
# Old zone → new parent (None = root)
PARENT_MAP = {
    # ── Roots ────────────────────────────────────────────────────────────
    "head":       None,
    "neck":       None,
    "torso":      None,
    "arms":       None,
    "groin":      None,
    "legs":       None,

    # ── HEAD children ────────────────────────────────────────────────────
    "hair":       "head",
    "face":       "head",
    "ears":       "head",

    # face children
    "eyes":       "face",
    "lips":       "face",
    "mouth":      "face",

    # mouth children
    "tongue":     "mouth",

    # ── NECK children ────────────────────────────────────────────────────
    "throat":     "neck",
    "nape":       "neck",

    # ── TORSO children ───────────────────────────────────────────────────
    "shoulders":  "torso",
    "chest":      "torso",
    "abdomen":    "torso",
    "back":       "torso",
    "waist":      "torso",

    # back children
    "lower_back": "back",

    # ── ARMS children ────────────────────────────────────────────────────
    "wrists":     "arms",
    "hands":      "arms",

    # ── LEGS children ────────────────────────────────────────────────────
    "hips":       "legs",
    "thighs":     "legs",
    "ankles":     "legs",
    "feet":       "legs",
}

# ---------------------------------------------------------------------------
# New zones to create if they don't exist on a character
# ---------------------------------------------------------------------------
# (name, parent, zone_type, intimate, visibility, consent_required)
NEW_ZONES = [
    # New root zones
    ("head",   None,    "surface",    False, "look",    "casual"),
    ("torso",  None,    "surface",    False, "look",    "casual"),
    ("groin",  None,    "surface",    True,  "hidden",  "intimate"),

    # New leaf zones
    ("mouth",  "face",  "both",       False, "look",    "casual"),
    ("tongue", "mouth", "attachment", False, "examine", "casual"),
]


def _make_zone(parent=None, zone_type="surface", intimate=False,
               visibility="look", consent_required="casual"):
    """Build a fresh zone dict matching the current _make_default_zone() format."""
    return {
        "nude":             "",
        "interior":         "",
        "covered_by":       None,
        "contents":         [],
        "ambient":          [],
        "zone_type":        zone_type,
        "intimate":         intimate,
        "visibility":       visibility,
        "consent_required": consent_required,
        "default":          True,
        "parent":           parent,
    }


def migrate_character(char, dry_run=False, verbose=True):
    """
    Migrate a single character's zones dict.

    Returns a dict of changes made:
        {
            "zones_updated": int,
            "zones_created": int,
            "parents_set":   int,
            "interior_added": int,
        }
    """
    raw = char.db.zones
    if raw is None:
        if verbose:
            print(f"  {char.key}: no zones attribute — skipping")
        return None

    def _plain(obj):
        """Recursively convert _SaverDict / _SaverList to plain Python types."""
        if isinstance(obj, dict):
            return {k: _plain(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_plain(i) for i in obj]
        return obj

    zones = _plain(raw)

    changes = {
        "zones_updated":  0,
        "zones_created":  0,
        "parents_set":    0,
        "interior_added": 0,
    }

    # ── Step 1: Backfill "parent" and "interior" on every existing zone ──
    for zname, zdata in zones.items():
        if not isinstance(zdata, dict):
            continue

        changed = False

        # Add "interior" if missing
        if "interior" not in zdata:
            if not dry_run:
                zdata["interior"] = ""
            changes["interior_added"] += 1
            changed = True

        # Set "parent" based on PARENT_MAP; for unknown freeform zones set None
        if "parent" not in zdata:
            new_parent = PARENT_MAP.get(zname, None)
            if not dry_run:
                zdata["parent"] = new_parent
            changes["parents_set"] += 1
            changed = True
        else:
            # Correct wrong parent if zone is in our known map
            if zname in PARENT_MAP and zdata.get("parent") != PARENT_MAP[zname]:
                if verbose:
                    old = zdata.get("parent")
                    new = PARENT_MAP[zname]
                    print(f"    {zname}: parent {old!r} → {new!r}")
                if not dry_run:
                    zdata["parent"] = PARENT_MAP[zname]
                changes["parents_set"] += 1
                changed = True

        if changed:
            changes["zones_updated"] += 1

    # ── Step 2: Promote existing zones that are now roots ────────────────
    # neck, arms, legs already existed as flat zones; now they are roots.
    for root_name in ("neck", "arms", "legs"):
        if root_name in zones and isinstance(zones[root_name], dict):
            if zones[root_name].get("parent") != None:  # noqa: E711
                if verbose:
                    print(f"    {root_name}: promoting to root (parent → None)")
                if not dry_run:
                    zones[root_name]["parent"] = None
                changes["parents_set"] += 1
                changes["zones_updated"] += 1

    # ── Step 3: Create brand-new zones that didn't exist before ──────────
    for (zname, parent, ztype, intimate, visibility, consent) in NEW_ZONES:
        if zname not in zones:
            if verbose:
                p = parent or "root"
                print(f"    creating zone '{zname}' (parent: {p})")
            if not dry_run:
                zones[zname] = _make_zone(
                    parent=parent,
                    zone_type=ztype,
                    intimate=intimate,
                    visibility=visibility,
                    consent_required=consent,
                )
            changes["zones_created"] += 1

    # ── Step 4: Write back ────────────────────────────────────────────────
    # Use attributes.add() instead of char.db.zones = zones.
    # Evennia's db shortcut does a serialization comparison before saving and
    # may skip the write if the top-level dict looks "the same" (e.g. same
    # keys, same object identity after deepcopy).  attributes.add() always
    # forces an unconditional database write.
    if not dry_run:
        char.attributes.add("zones", zones)

    return changes


def run(dry_run=False, verbose=True):
    """
    Run the migration against every character in the database.

    Args:
        dry_run (bool): If True, report what would change without saving.
        verbose (bool): If True, print per-character detail.
    """
    char_path = getattr(settings, "BASE_CHARACTER_TYPECLASS",
                        "typeclasses.characters.Character")

    chars = ObjectDB.objects.filter(db_typeclass_path=char_path)
    total = chars.count()

    if dry_run:
        print(f"[DRY RUN] Zone migration — {total} character(s) found\n")
    else:
        print(f"Zone migration — {total} character(s) found\n")

    grand = {
        "zones_updated":  0,
        "zones_created":  0,
        "parents_set":    0,
        "interior_added": 0,
        "skipped":        0,
    }

    for char in chars:
        if verbose:
            print(f"• {char.key} (pk={char.pk})")
        result = migrate_character(char, dry_run=dry_run, verbose=verbose)
        if result is None:
            grand["skipped"] += 1
            continue
        for k in ("zones_updated", "zones_created", "parents_set", "interior_added"):
            grand[k] += result[k]

    print()
    print("=" * 50)
    if dry_run:
        print("DRY RUN — no data was written")
    else:
        print("Migration complete")
    print(f"  Characters processed : {total - grand['skipped']}")
    print(f"  Characters skipped   : {grand['skipped']}")
    print(f"  Zones updated        : {grand['zones_updated']}")
    print(f"  Zones created        : {grand['zones_created']}")
    print(f"  Parents set/fixed    : {grand['parents_set']}")
    print(f"  Interior keys added  : {grand['interior_added']}")
    print("=" * 50)


# ---------------------------------------------------------------------------
# Evennia runscript entry point
# ---------------------------------------------------------------------------
# When called via `evennia run world/zone_migration.py`, Evennia executes the
# module and then looks for a callable named `run` or just runs module-level
# code.  We call run() at module level so it works with both interfaces.
# ---------------------------------------------------------------------------
if __name__ == "__main__" or globals().get("EVENNIA_RUN"):
    run()
