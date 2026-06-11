"""
world/post_office_build.py — staffing and expanding the Postal Office.

Run as staff:  @py from world.post_office_build import build_post_office; build_post_office(me)

Idempotent. It:
  1. Finds the Postal Office (by name, else #32 per the design doc).
  2. Spawns the three clerks as REAL present NPCs — Seraphine / Calix / Vesper — with their
     canonical look-descs (design/post_office.md; characterized in ogram_commands.py).
  3. Digs and connects two new rooms:
       • the SORTING HALL (behind the counter) — the ogram system's guts, with the Dead
         Letter Cage (a readable easter egg of filthy unclaimed mail).
       • the QUIET ROOM (off the hall) — Seraphine's officiating nook, where contracts get
         signed on the chaise and her margin-pen does its quiet work (post_office.officiate
         flavour made architectural). Easter eggs: her amendments drawer, Calix's wax kit,
         Vesper's PENDING tray.
  4. Deepens all three rooms' ambient pools (the office's pool is merged, not replaced).

Everything is tagged ("post_office", category="area") so teardown can be precise. Fixtures
are un-gettable with in-voice get_err_msgs. No gating anywhere; this is a public branch.
"""

from evennia import search_object
from evennia.utils import create

_TAG = ("post_office", "area")


# ── the clerks (canonical descs from design/post_office.md) ───────────────────
_CLERKS = [
    ("Seraphine",
     "Seraphine occupies the left end of the counter the way she seems to occupy most "
     "spaces — entirely, and without apology. Crimson-skinned, small swept-back horns, a "
     "tail that moves with an expressiveness she doesn't bother to suppress. She is reading "
     "the front of a sealed letter with the expression of someone who could absolutely open "
     "it if she wanted to and has chosen, generously, not to. She looks up when the room "
     "changes. She takes you in with the particular warmth of a woman who has heard every "
     "kind of secret and found most of them charming rather than shocking."),
    ("Calix",
     "Calix stands at the center of the counter with the unhurried solidity of something "
     "built to last. Deep charcoal skin, ram horns, the broad-shouldered patience of a man "
     "who has carried stranger parcels than this in worse weather and arrived looking "
     "entirely unbothered. He is sealing a letter with three precise impressions of the "
     "stamp — no more, no fewer. He glances up without expression. The glance holds a beat "
     "longer than necessary. He returns to his work as though you'd imagined the extra "
     "beat, which is probably what he intended."),
    ("Vesper",
     "Vesper is at the far right of the counter, their attention apparently absorbed by a "
     "sorting task that doesn't seem to need quite this much focus. Opalescent skin. "
     "Swept-back horns that catch the lamplight differently every time you look. Their "
     "eyes, when they briefly track across the room, are silver — then a color that sits "
     "somewhere between violet and something that doesn't translate. They are holding a "
     "letter marked |xAffection — Grope — Anonymous|n with the focused neutrality of "
     "someone who processes these regularly and has developed a professional relationship "
     "with the fact."),
]

# Office ambient additions — the clerks alive at their stations (merged into the pool).
_OFFICE_AMBIENT = [
    "|xSeraphine holds a sealed envelope to the lamplight, reads something through the paper "
    "that makes her smile like a cat in cream, and files it — unopened — under 'urgent'.|n",
    "|xCalix weighs a parcel that is very faintly moving, notes the weight, and stamps it "
    "LIVE CARGO — HANDLE WARMLY without any change of expression whatsoever.|n",
    "|xVesper sorts a stack marked CONFESSIONS into pigeonholes by some system that involves "
    "blushing exactly twice and pretending, both times, that they didn't.|n",
    "|xA pneumatic tube somewhere behind the counter receives something with a wet, satisfied "
    "thunk. None of the clerks react. Regulars learn not to ask. Eventually.|n",
    "|xSeraphine murmurs something to Calix that makes the tips of his ears darken. He stamps "
    "the next three letters in perfect rhythm anyway. Vesper files the exchange under "
    "'witnessed'.|n",
]

# ── the Sorting Hall ──────────────────────────────────────────────────────────
_SORTING_DESC = (
    "Behind the counter, the office stops pretending to be quaint. The Sorting Hall is a "
    "long warm chamber ribbed with brass pneumatic tubes that hiss and shudder like a "
    "sleeping animal, racks of pigeonholes rising to the ceiling on rolling ladders, every "
    "slot labelled in three different clerks' handwriting — Seraphine's looping warmth, "
    "Calix's draftsman capitals, Vesper's careful, anonymous print. Half the labels are "
    "ordinary. The other half are the office's real trade: |xLONGING — UNSIGNED|n, "
    "|xPROPOSITIONS (EXPLICIT) — AWAITING COURAGE|n, |xTO BE READ ALOUD, BLINDFOLDED|n, "
    "|xRETURNED: TOO MUCH, APPARENTLY|n. At the far end, under a hooded lamp, stands the "
    "Dead Letter Cage — black iron, triple-locked, and fuller than any honest town should "
    "make it."
)
_SORTING_AMBIENT = [
    "|xA tube delivers a letter so warm to the touch that the receiving basket is lined with "
    "felt specifically for them. It joins several others, all faintly steaming.|n",
    "|xThe rolling ladder glides past on its own — or Vesper was on it a second ago and has "
    "relocated with suspicious efficiency to the far end, very interested in slot 9-C.|n",
    "|xSomething in the Dead Letter Cage settles, papery and patient, like a nest "
    "rearranging itself around its own secrets.|n",
    "|xTwo letters in adjacent pigeonholes are addressed to each other. The clerks have left "
    "them side by side, and nobody will say which of them did it.|n",
]
_CAGE_DESC = (
    "The Dead Letter Cage: black iron, waist-high, triple-locked, and stuffed. This is where "
    "the undeliverable ends up — and in a town like this, 'undeliverable' is rarely about the "
    "address. Through the bars you can read fragments of the unclaimed: a confession to a "
    "neighbour's wife that runs to nine pages and gets considerably less repentant as it "
    "goes; a parcel tag reading |xCONTENTS: WORN, AS REQUESTED — COLLECT IN PERSON OR NOT AT "
    "ALL|n; an envelope addressed only |xto the one who watches me from the bakery, yes, you, "
    "I leave the curtains open ON PURPOSE|n; and a single letter, very old, very handled, "
    "marked in Seraphine's hand: |xdelivered eventually. they always are.|n The cage's "
    "third lock, you notice, is decorative. The letters stay because they're not done "
    "ripening."
)

# ── the Quiet Room ────────────────────────────────────────────────────────────
_QUIET_DESC = (
    "Off the Sorting Hall, behind a curtain heavy enough to mean it, is the Quiet Room — "
    "the office's confessional, notary's nook, and (by appointment, which is to say by "
    "Seraphine's mood) something rather warmer. A deep chaise in oxblood leather, worn "
    "shiny in patterns that tell their own story. A writing desk with three inkwells: "
    "Calix's black, Vesper's grey, and Seraphine's — a red that catches the light like it's "
    "still wet. This is where contracts come to be officiated: read flat by Calix, riddled "
    "by Vesper, or kissed through by Seraphine, whose margins have a way of acquiring "
    "clauses. The lamp is always low. The pen is always warm. The door, famously, has no "
    "lock — the office insists on that, and won't say why, and the why is kindness."
)
_QUIET_AMBIENT = [
    "|xThe chaise creaks its old oxblood creak, settling, as though remembering a signature "
    "that took considerably longer than the document required.|n",
    "|xSeraphine's red inkwell sits exactly where it was — but fuller, somehow, than it was "
    "an hour ago. Nobody refills it. Nobody has ever been seen refilling it.|n",
    "|xFrom the hall beyond the curtain, Calix's stamp lands three times — pause — three "
    "times. The rhythm of a man giving someone, somewhere, time to change their mind.|n",
]
_DRAWER_DESC = (
    "Seraphine's amendments drawer — unlocked, naturally; she files her sins where anyone "
    "could read them, which is its own kind of confidence. Inside: fair copies of contracts "
    "she's officiated, each with her red marginalia faithfully preserved. |x'…and the "
    "signee will warm to me, a little, each time we meet; this clause to be remembered "
    "fondly when discovered.'|n |x'…and on discovery of this clause, the signee owes the "
    "officiant one (1) secret, freely told, of equal weight.'|n |x'…and the officiant "
    "retains the right to attend any consummation hereunder in a strictly supervisory "
    "capacity, supervision to include refreshments.'|n A note atop the stack, to no one: "
    "|xthey always read the drawer eventually. hello, sweet thing. that one's yours now "
    "too.|n — and you may consider that one binding, since you read it."
)
_WAXKIT_DESC = (
    "Calix's wax kit: a rack of seals in disciplined rows, each die labelled in his "
    "draftsman capitals. PRIVATE. URGENT. PERISHABLE. Then the working row, the ones the "
    "town actually pays for: |xBINDING|n, |xWITNESSED|n, |xWORN AGAINST SKIN IN TRANSIT (CERTIFIED)|n, "
    "and one die, kept apart in a velvet groove and warm to the touch though the brazier's "
    "cold, marked only |xHERS|n. The kit's care instructions are written inside the lid: "
    "|xWax takes the shape it's pressed with. So does everything. — C.|n"
)
_PENDING_DESC = (
    "Vesper's PENDING tray, squared to the desk edge at an angle that took longer than "
    "squaring it would have. In it: the letter marked |xAffection — Grope — Anonymous|n "
    "(third week running; Vesper re-files it daily, always to the top); a form titled "
    "DECLARATION OF NATURE, blank for years, in which the office has never once pressured "
    "them to fill anything; and a note in Seraphine's red ink — |xwhenever you're ready, "
    "love. or never. both are allowed here.|n — that has been picked up, refolded, and "
    "replaced so many times the creases have creases. You put it back exactly as you "
    "found it. Some pending things are doing fine as they are."
)


def _tag(obj):
    try:
        obj.tags.add(_TAG[0], category=_TAG[1])
    except Exception:
        pass
    return obj


def _find_office():
    """The Postal Office — by name, else the design doc's #32."""
    for term in ("The Postal Office", "Postal Office"):
        res = search_object(term)
        if res:
            return res[0]
    res = search_object("#32")
    return res[0] if res else None


def _fixture(key, desc, room, err):
    """An un-gettable readable fixture (idempotent by key within the room)."""
    if any((o.key or "").lower() == key.lower() for o in room.contents):
        return None
    f = _tag(create.create_object("typeclasses.objects.Object", key=key, location=room))
    f.db.desc = desc
    try:
        f.locks.add("get:false()")
        f.db.get_err_msg = err
    except Exception:
        pass
    return f


def build_post_office(caller):
    office = _find_office()
    if not office:
        caller.msg("|rCan't find the Postal Office (by name or #32).|n")
        return
    report = []

    # 1. The clerks, spawned at their stations (idempotent by name).
    try:
        from typeclasses.npc import NPC
        present = {(o.key or "").lower() for o in office.contents}
        for name, desc in _CLERKS:
            if name.lower() in present:
                continue
            n = _tag(create.create_object(NPC, key=name, location=office))
            n.db.rp_name = name
            n.db.physical_desc = desc
            report.append(f"clerk {name}")
    except Exception as e:
        caller.msg(f"|rClerk spawn issue: {e}|n")

    # 2. Office ambient — merged, never replaced.
    amb = list(getattr(office.db, "ambient_msgs", None) or [])
    added = 0
    for line in _OFFICE_AMBIENT:
        if line not in amb:
            amb.append(line)
            added += 1
    office.db.ambient_msgs = amb
    if added:
        report.append(f"{added} office ambient lines")

    # 3. The Sorting Hall (behind the counter).
    hall = next((e.destination for e in office.exits
                 if e.destination and "sorting" in (e.destination.key or "").lower()), None)
    if not hall:
        hall = _tag(create.create_object("typeclasses.rooms.Room", key="The Sorting Hall"))
        hall.db.desc = _SORTING_DESC
        hall.db.ambient_msgs = list(_SORTING_AMBIENT)
        create.create_object("typeclasses.exits.Exit", key="behind the counter",
                             aliases=["counter", "sorting", "back"],
                             location=office, destination=hall)
        create.create_object("typeclasses.exits.Exit", key="front office",
                             aliases=["front", "office", "out"],
                             location=hall, destination=office)
        report.append("the Sorting Hall (+exits)")
    _fixture("the dead letter cage", _CAGE_DESC, hall,
             "The cage is bolted down, triple-locked, and frankly it's the letters that "
             "would object — they're not done ripening.")

    # 4. The Quiet Room (off the hall).
    quiet = next((e.destination for e in hall.exits
                  if e.destination and "quiet" in (e.destination.key or "").lower()), None)
    if not quiet:
        quiet = _tag(create.create_object("typeclasses.rooms.Room", key="The Quiet Room"))
        quiet.db.desc = _QUIET_DESC
        quiet.db.ambient_msgs = list(_QUIET_AMBIENT)
        create.create_object("typeclasses.exits.Exit", key="the heavy curtain",
                             aliases=["curtain", "quiet", "quiet room"],
                             location=hall, destination=quiet)
        create.create_object("typeclasses.exits.Exit", key="back through the curtain",
                             aliases=["hall", "out", "back"],
                             location=quiet, destination=hall)
        report.append("the Quiet Room (+exits)")
    _fixture("seraphine's amendments drawer", _DRAWER_DESC, quiet,
             "The drawer slides out, not away. Her sins are filed, not portable.")
    _fixture("calix's wax kit", _WAXKIT_DESC, quiet,
             "It weighs more than it looks like it weighs, and it looks like it knows it.")
    _fixture("vesper's pending tray", _PENDING_DESC, quiet,
             "You put it back exactly as you found it. Some pending things are doing fine "
             "as they are.")

    caller.msg("|gPost office staffed and expanded:|n " + (", ".join(report) or "nothing new "
               "(already complete)") + "|n\n|x  (look seraphine/calix/vesper · behind the "
               "counter · the heavy curtain · read the cage/drawer/kit/tray)|n")
