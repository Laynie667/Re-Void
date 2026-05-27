"""
One-time zone migration helper.
Run from in-game with:  @py from world import fix_zones
"""

def _plain(obj):
    """Recursively strip Evennia _SaverDict/_SaverList proxies.
    Uses hasattr instead of isinstance so it works even when _SaverDict
    does not inherit from dict."""
    if hasattr(obj, 'items'):
        return {k: _plain(v) for k, v in obj.items()}
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        return [_plain(i) for i in obj]
    return obj


PARENT_MAP = {
    "head": None, "neck": None, "torso": None,
    "arms": None, "groin": None, "legs": None,
    "hair": "head", "face": "head", "ears": "head",
    "eyes": "face", "lips": "face", "mouth": "face", "tongue": "mouth",
    "throat": "neck", "nape": "neck",
    "shoulders": "torso", "chest": "torso", "abdomen": "torso",
    "back": "torso", "lower_back": "back", "waist": "torso",
    "wrists": "arms", "hands": "arms",
    "hips": "legs", "thighs": "legs", "ankles": "legs", "feet": "legs",
}


def fix(char):
    zones = _plain(char.db.zones)
    for zname, zdata in zones.items():
        if "parent" not in zdata:
            zdata["parent"] = PARENT_MAP.get(zname, None)
        if "interior" not in zdata:
            zdata["interior"] = ""
    char.attributes.add("zones", zones)
    print(f"Fixed {char.key}:")
    for k, v in zones.items():
        print(f"  {k}: parent={v.get('parent', 'MISSING')!r}")


# Run immediately on import against the caller — works with @py
from evennia import search_object
from django.conf import settings
from evennia.objects.models import ObjectDB

char_path = getattr(settings, "BASE_CHARACTER_TYPECLASS",
                    "typeclasses.characters.Character")
chars = list(ObjectDB.objects.filter(db_typeclass_path=char_path))
print(f"Found {len(chars)} character(s)")
for c in chars:
    fix(c)
