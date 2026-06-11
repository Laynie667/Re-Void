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

    # 5. The siblings' private pocket rooms (off the hall / the quiet room).
    try:
        _build_pockets(office, hall, quiet, report)
    except Exception as e:
        caller.msg(f"|rPocket-room build issue: {e}|n")

    caller.msg("|gPost office staffed and expanded:|n " + (", ".join(report) or "nothing new "
               "(already complete)") + "|n\n|x  (look seraphine/calix/vesper · behind the "
               "counter · the heavy curtain · the mirror / strong door / fold in the corner · "
               "read the cage/drawer/kit/tray/toyboxes · |wclerk|x at the counter to talk)|n")


# ═══════════════════════════════════════════════════════════════════════════
# PART TWO — the siblings' pocket rooms, their toyboxes, and the counter menu
# (CYOA-driven: no say-triggers; `counter` opens the menu, choose <n> drives it)
# ═══════════════════════════════════════════════════════════════════════════

_SERA_ROOM_DESC = (
    "Behind the Quiet Room's standing mirror — which swings like a door if you know to push "
    "the left edge, and Seraphine always somehow already knows you know — is her parlour-"
    "within-the-parlour. It is exactly what you'd expect and worse: deep cushions in sin "
    "colours, a daybed with restraint points disguised as upholstery buttons, shelves of "
    "keepsakes each tagged in her looping hand with a name and a date and, occasionally, a "
    "small heart. The air smells of her — warm wax, clove, something underneath that makes "
    "you want to confess. A teapot steams perpetually for guests who stopped being able to "
    "leave promptly and then stopped wanting to. The mirror, from this side, is a window."
)
_SERA_ROOM_AMBIENT = [
    "|xThe teapot refreshes itself with a contented little gurgle. It has opinions about "
    "guests who don't stay for a second cup, and the cushions agree.|n",
    "|xOne of the tagged keepsakes on the shelf — a collar? a garter? it's dark in that "
    "corner, deliberately — turns very slightly toward you, like a sunflower.|n",
    "|xThrough the one-way mirror, the Quiet Room sits empty and patient. Seraphine likes "
    "to watch people decide things in there. She says the deciding is the best part.|n",
]
_SERA_TOYBOX_DESC = (
    "Seraphine's toybox — a steamer trunk in oxblood leather to match the chaise, brass-"
    "cornered, unlocked (her confidence again). The tray on top is the public layer: silk "
    "rope coiled in perfect figure-eights, a feather she calls 'the negotiator', wax in "
    "votive rows by melting point, each labelled with a name of someone who 'sat for' that "
    "shade. Beneath the tray, the second layer: the harness with the post-office stamp on "
    "the saddle (|x'official business'|n, the tag insists), a blindfold of letter-paper "
    "('so they can feel themselves being read'), and a worn deck of delivery slips repurposed "
    "as a punishment lottery — REDIRECTED, POSTAGE DUE, HANDLE WITH CARE, OPENED BY MISTAKE, "
    "each with a forfeit on the back in red ink that gets steadily less postal. At the very "
    "bottom, wrapped in tissue: a tiny knitted tail. A note pinned to it: |xVesper's first "
    "try. They threw it at me. I keep everything. — S.|n"
)
_SERA_SECRET_DESC = (
    "A hatbox of letters the siblings wrote each other and never sent — Seraphine keeps "
    "them, of course she does. Calix's, draftsman-neat: |x'You laugh too loudly at my "
    "expense at the counter. (Do not stop.)'|n Vesper's, in careful anonymous print: "
    "|x'S — if I ever do fill in the form, you are not allowed to throw a party. A small "
    "dinner. Maybe. — V.'|n And one of her own, addressed to both, sealed with the HERS "
    "die, marked: |xfor when one of us finally falls in love with a customer and has to be "
    "laughed at properly. (I assume it will be Calix.) (It will be Calix.)|n"
)

_CALIX_ROOM_DESC = (
    "The strong door off the Sorting Hall opens on Calix's keeping-room, and it is the "
    "tidiest erotic space in the known world. Everything racked, everything squared: "
    "restraints graded by width on brass pegs, gags arranged by *silence achieved* (the "
    "labels are measured in decibels), a single immaculate bench with its wear patterns "
    "sanded and re-oiled until they read as design. One wall is a postal sorting-grid "
    "repurposed: each pigeonhole holds one item and one card in his capitals — 3RD BELL "
    "TUESDAY. THE QUIET ONE. ASKED TWICE, ANSWERED ONCE. He files his memories the way he "
    "files everything: precisely, privately, and with no system anyone else can read, which "
    "is the entire point. It smells of saddle soap and patience."
)
_CALIX_ROOM_AMBIENT = [
    "|xA strap on the third peg is fractionally crooked. You could swear it wasn't a moment "
    "ago. Somewhere, Calix's shoulders itch.|n",
    "|xThe bench creaks once, settling — a precise, load-bearing creak, like a man clearing "
    "his throat before saying something important and then not saying it.|n",
    "|xOne pigeonhole card reads, simply, |wSTAYED.|x No item in that slot. The emptiness is "
    "the keepsake.|n",
]
_CALIX_TOYBOX_DESC = (
    "Calix's toybox is a footlocker that opens in total silence — he oils the hinges weekly, "
    "which tells you everything about how it gets used. Contents racked in fitted felt: a "
    "wax kit twin to the one in the Quiet Room but with one extra die, un-labelled, its face "
    "worn too smooth to read by eye (touch suggests a name; touching it feels like being "
    "caught at something); cord in postal twine-weights from 'parcel' to 'confession'; and a "
    "small brass counting-frame, beads worn bright, with a card: |xfor counting. she knows "
    "what.|n Under the felt, flat and face-down, one framed delivery receipt — signature "
    "line signed twice, the second time steadier. He keeps the proof that someone, once, "
    "needed two tries to consent and made the second one *certain*. It is the most Calix "
    "object that has ever existed."
)
_CALIX_SECRET_DESC = (
    "Wedged behind the rack, a single page in Seraphine's hand that Calix has confiscated "
    "but — note — not destroyed: |x'TO THE STAFF NOTICEBOARD: be advised that our Calix "
    "re-sands the consultation bench after certain appointments and re-oils it after one (1) "
    "appointment in particular, recurring, and has done for two years, and thinks none of us "
    "have noticed the pattern in the calendar. We have noticed the pattern in the calendar. "
    "— with love, the management (S.)'|n On the back, in Calix's capitals, one word, pressed "
    "so hard it's nearly through the paper: |wDON'T.|n He kept her note. He kept his answer "
    "to it. He filed both. That's the whole man, right there."
)

# ── Vesper's nest ─────────────────────────────────────────────────────────────
_VESPER_ROOM_DESC = (
    "There is no door to Vesper's room. There is a fold in the Sorting Hall's far corner — a "
    "place the pigeonholes don't quite meet the wall — and if you've been let in, you've "
    "always been able to find it, and if you haven't, there was never a corner there at all. "
    "Inside: a burrow. Soft past reason — nested blankets, lamplight the colour of held "
    "breath, no hard edges anywhere, the safest-feeling room in the building. The walls are "
    "hung with mirrors, every one of them draped — except the tall one by the nest, which is "
    "undraped only in here, only when they're alone, because this is the one place Vesper "
    "tries things on and lets themself look. The toybox sits at the foot of the nest like a "
    "patient pet. The air doesn't smell of anything. That's deliberate too. They like to be "
    "the one thing in a room with no declared nature, and here, finally, nobody's asking."
)
_VESPER_ROOM_AMBIENT = [
    "|xThe undraped mirror shows you, then — for the length of a blink, with no malice in it — "
    "shows you slightly *more* you than you are, the way Vesper must practise seeing.|n",
    "|xA blanket rearranges itself into a slightly more enclosing shape around wherever you've "
    "settled. The nest takes care of its guests. It doesn't ask first.|n",
    "|xSomething in the toybox shifts with a soft articulate clack, like a thing turning over "
    "in its sleep, trying on a dream of being held.|n",
]
_VESPER_TOYBOX_DESC = (
    "Vesper's toybox: a lacquered chest, the black of it shot through with shifting "
    "opal like their skin, and it does not lock because what's inside doesn't believe in "
    "staying put. The top tray is a wardrobe of *parts* — this is the secret Seraphine tells "
    "and Vesper would die before confirming. Cocks in a graded rack from modest to "
    "architectural, each one warm. Cunts and holes of every described and a few undescribed "
    "kinds, soft-bodied, nested in velvet. A pair of horns that aren't theirs and a tail "
    "that is. Things labelled only |x'a change'|n, |x'another change'|n, |x'this one was a "
    "mistake (keep)'|n. Vesper tries them on — alone, in front of the one undraped mirror — "
    "tries on being a thing with a fixed shape, wears it an hour, and puts it carefully back, "
    "every time. Tucked in the lid, two cards. Seraphine's: |xtried-on is still you, sweet "
    "thing. so is put-away. — S.|n Under it, Vesper's reply, never delivered, just kept where "
    "she'd find it if she went looking, which she has: |xi know. thank you. stop reading my "
    "toybox. — V.|n"
)
_VESPER_SECRET_DESC = (
    "Pinned inside the nest where only a guest curled in it would see: the DECLARATION OF "
    "NATURE form, the real one, not the office copy — and this one isn't blank. It's been "
    "filled in and erased so many times the paper's gone soft as cloth. You can make out the "
    "ghosts of every answer they tried and took back: a word, scrubbed out. A different word, "
    "scrubbed out. Once, just |xyes|n, to a question that isn't printed on the form, scrubbed "
    "out hardest of all. At the bottom, not erased, in fresh grey ink: |xleaving it open is "
    "an answer. the open is the answer. (S. keeps trying to throw me a party about this. there "
    "will be no party.)|n"
)

# ── Seraphine gossips (the half-tutorial, half-anecdote pool) ─────────────────
# Each is a fond, filthy, load-bearing little story she tells across the counter. They
# double as worldbuilding and as the warm bait of her character. Prose-only; no effect.
_GOSSIP = [
    ("Vesper and the toybox",
     "Seraphine leans on the counter, delighted to have been asked. \"Oh, you want the "
     "*good* stories.\" She lowers her voice to the register of a woman doing you a great "
     "and slightly cruel favour. \"I once caught Vesper trying on different parts. In the "
     "nest, thought they'd folded the corner shut behind them — they hadn't, quite. Standing "
     "in front of that mirror they keep draped everywhere else, wearing a cock that wasn't "
     "the one they'd worn the morning before, turning, *checking*, the way you'd check a hem. "
     "Then a different hole, fitted soft and careful, and they made this little sound — not "
     "arousal, sweet thing, *relief*, like setting down something heavy. It was the most "
     "honest I've ever seen them. I backed out before they caught me. Left a card in the lid. "
     "We've never spoken of it.\" She straightens, fond as anything. \"They put everything "
     "back, after. They always put everything back. That's the part that gets me.\""),
    ("Calix and the bench",
     "\"Calix,\" she says, like the name is a sweet she's been saving. \"Our Calix re-sands "
     "that consultation bench of his after a hard appointment — fine, sensible. But there's "
     "*one* name in his calendar he re-oils it for. Two years running. Same little gap left in "
     "the schedule on either side, so nobody's booked in too close. He thinks the precision "
     "hides it. The precision is how I *found* it.\" She taps the counter. \"I wrote it up for "
     "the noticeboard once, as a joke. He confiscated the note and kept it. Wrote DON'T on the "
     "back and kept *that*. Filed them together.\" A slow, warm smile. \"He's going to fall in "
     "love so hard one day it'll reorganise his entire filing system, and I am going to be "
     "*unbearable* about it.\""),
    ("the letters they never sent",
     "\"We write each other letters,\" Seraphine admits, \"the three of us. And never send "
     "them — that's the whole game. You write the true thing, you seal it, you don't deliver "
     "it, and somehow we all end up reading each other's anyway. Postal family.\" She turns a "
     "sealed envelope over in her clever fingers. \"Calix's are one line and devastating. "
     "Vesper's apologise for things they haven't done yet. Mine —\" the smile turns inward, "
     "private \"— mine tend to be instructions for after I'm gone. Who gets the red ink. Who "
     "gets *you*, if it comes to that.\" She sets the letter down. \"Don't look so alarmed, "
     "sweet thing. I said if.\""),
    ("how officiating actually works",
     "\"Since you're here to learn the trade and not just to be charmed — though do both — "
     "here's how a contract gets *officiated*.\" She counts it on her fingers, warm and brisk. "
     "\"You draft it: |wcontract draft|n, then |wcontract clauses|n to read what's on it. "
     "Then you bring it to one of us at the counter. Calix reads it flat — every word, no "
     "weather in his voice, so you hear exactly what you're signing. Vesper riddles it — "
     "finds the second meaning, the door you didn't know you left open. And me —\" she "
     "produces the red inkwell as if from nowhere \"— I officiate by *kissing it through*. "
     "|wofficiate|n, |wcosign|n, and it's done. My margins have a way of acquiring clauses "
     "between the reading and the signing. Everyone's warned. Almost everyone signs anyway. "
     "That's not me being wicked, that's just what people *want*, dressed up enough to say "
     "yes to.\""),
    ("why the doors don't lock",
     "Her warmth doesn't dim, but it changes weight. \"You'll notice the Quiet Room's got no "
     "lock. None of the rooms that *matter* do. People assume it's an oversight, or charm.\" "
     "She holds your eye, and for once there's no performance in it. \"It's the floor, sweet "
     "thing. I will write you into the most binding, breathless, can't-look-away arrangement "
     "this office has ever sealed — and the door will be unlocked the whole time, and you "
     "could walk, and we both know you won't, and *that's* the thing I actually collect. Not "
     "people who can't leave. People who can and stay.\" Then the brightness floods back in. "
     "\"Anyway! Stamps are two coppers. Do you want to hear about Vesper's toybox?\""),
    ("the bakery watcher",
     "\"Down in the Dead Letter Cage,\" she says, conspiratorial, \"there's a letter — open "
     "curtains, on purpose, *yes you, from the bakery*. Came in unsigned years ago. Properly "
     "filthy. We could've binned it.\" She shrugs, pleased. \"Instead Calix re-files it every "
     "season so it stays ripe, and twice a year the baker comes in 'about a parcel' and "
     "stands very close to that cage and reads through the bars and leaves pink to the ears "
     "and buys a stamp they never use.\" A delighted little exhale. \"We are not, strictly, a "
     "post office. We are a place where the things people can't say get to *keep existing* "
     "until they can. The mail is mostly a pretext. You'll see.\""),
    ("Vesper and the holes",
     "She glances toward the fold in the corner, voice dropping to honey. \"You got the part "
     "about Vesper trying on *parts*. Here's the one I've never told a soul.\" A slow, fond "
     "smile. \"It's not only cocks they fit, sweet thing. I came back for a forgotten ledger "
     "and there they were at the mirror, having tried on a *hole* — soft-bodied, the kind from "
     "the bottom of the toybox — fitted it careful as anything and then just... *stood* there, "
     "one hand pressed to it, eyes shut, learning the shape of being a thing that could be "
     "*filled*. Not even touching it for the want of it. For the *knowing*.\" Her tail goes "
     "still. \"They breathed out like they'd set something heavy down. Tried on being takeable "
     "for an hour, then put it back in its velvet and squared the box. I have never wanted so "
     "badly to knock and never been so sure I shouldn't. Left them a card. You've read the "
     "card.\""),
    ("Calix's one indulgence",
     "\"Everyone thinks Calix wants nothing,\" she says, delighted to correct it. \"Wrong. "
     "Our Calix has exactly *one* indulgence and he is mortified by it. He likes to be told "
     "he did it *right*. That's all. You stamp a thing for him, fold a parcel to his "
     "standard, and tell him — plainly, no teasing — 'that's perfect, Calix,' and the man "
     "goes the most beautiful charcoal-darker you've ever seen and cannot speak for a full "
     "three seconds.\" She mimes his careful little throat-clear. \"I discovered it by "
     "accident and I ration it like spun sugar, because the day he realises I know, he'll "
     "build a filing system to hide it in. Don't tell him. *Do* tell him he did it right.\""),
    ("the three a.m. drawer",
     "\"There's a drawer in my parlour,\" she says, suddenly quieter, the warmth turning "
     "true, \"labelled *things said at 3 a.m.* It's the realest one. Vesper confessing they "
     "don't actually want to be unreadable, they just don't know how to be read *gently*. "
     "Calix admitting the empty pigeonhole marked STAYED is about someone who didn't. Me —\" "
     "she stops, and for once the performance drops clean off her face \"— me, in my own "
     "looping hand, that I collect people because a full house is the only thing that's ever "
     "quieted the part of me that's sure I'll end up an unclaimed letter myself.\" Then the "
     "bright smile snaps back, seamless. \"Anyway! You didn't hear that. It was 3 a.m. "
     "somewhere. Stamp?\""),
    ("how the three of them happened",
     "\"We're not blood, before you ask — everyone asks.\" She arranges three letters into a "
     "neat fan, fond. \"Calix came first, carrying parcels nobody else would touch. Then me, "
     "talking my way behind the counter and never leaving. Vesper just... *appeared* one "
     "winter, sorting mail like they'd always been here, and none of us could remember hiring "
     "them and none of us asked.\" A wink. \"We chose each other the way you choose to keep a "
     "stray that's already decided it lives with you. Family's just a long enough habit of not "
     "leaving. We're very good at not leaving. It's rather the whole business.\""),
]


def _build_pockets(office, hall, quiet, report):
    """Dig the three siblings' pocket rooms off the public spaces + place their fixtures.
    Idempotent: re-running won't duplicate rooms, exits, or fixtures. No gating (§0):
    these are private, but the way in and the way out are always open."""

    def _dig(anchor, key, desc, ambient, in_key, in_aliases, out_key, out_aliases):
        room = next((e.destination for e in anchor.exits
                     if e.destination and key.lower() in (e.destination.key or "").lower()), None)
        if not room:
            room = _tag(create.create_object("typeclasses.rooms.Room", key=key))
            room.db.desc = desc
            room.db.ambient_msgs = list(ambient)
            create.create_object("typeclasses.exits.Exit", key=in_key, aliases=in_aliases,
                                 location=anchor, destination=room)
            create.create_object("typeclasses.exits.Exit", key=out_key, aliases=out_aliases,
                                 location=room, destination=anchor)
            report.append(f"{key} (+exits)")
        return room

    # Seraphine's parlour — through the standing mirror in the Quiet Room.
    sera = _dig(quiet, "Seraphine's Parlour", _SERA_ROOM_DESC, _SERA_ROOM_AMBIENT,
                "the standing mirror", ["mirror", "parlour", "parlor"],
                "back through the mirror", ["mirror", "out", "quiet"])
    _fixture("seraphine's toybox", _SERA_TOYBOX_DESC, sera,
             "It's hers. You may look. Looking is most of what she wanted from you anyway.")
    _fixture("the hatbox of unsent letters", _SERA_SECRET_DESC, sera,
             "The hatbox stays. The letters were never going anywhere — that's the point of them.")

    # Calix's keeping-room — through the strong door off the Sorting Hall.
    calix = _dig(hall, "Calix's Keeping-Room", _CALIX_ROOM_DESC, _CALIX_ROOM_AMBIENT,
                 "the strong door", ["door", "keeping-room", "keeping room", "calix"],
                 "the strong door", ["door", "out", "hall", "sorting"])
    _fixture("calix's toybox", _CALIX_TOYBOX_DESC, calix,
             "He oiled the hinges so it would open in silence, not so it would leave with you.")
    _fixture("the confiscated note", _CALIX_SECRET_DESC, calix,
             "He confiscated it once already. He's not letting it walk now.")

    # Vesper's nest — through the fold in the Sorting Hall's corner.
    vesper = _dig(hall, "Vesper's Nest", _VESPER_ROOM_DESC, _VESPER_ROOM_AMBIENT,
                  "the fold in the corner", ["fold", "corner", "nest", "vesper"],
                  "out of the fold", ["fold", "out", "hall", "sorting"])
    _fixture("vesper's toybox", _VESPER_TOYBOX_DESC, vesper,
             "Tried-on is still you. So is put-away. So is leaving it where it lives.")
    _fixture("the declaration form", _VESPER_SECRET_DESC, vesper,
             "Leaving it open is an answer. You leave it open.")

    return sera, calix, vesper

