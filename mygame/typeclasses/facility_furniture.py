"""
typeclasses/facility_furniture.py

Real fixtures for the facility. FacilityFurniture can't be picked up and reads
as installed equipment. FacilityBoard renders the subject's LIVE processing
board when looked at, so 'look the status board' is always current.
"""

from evennia import DefaultObject


class FacilityFurniture(DefaultObject):
    """A fixed piece of facility equipment — described, lookable, un-gettable."""

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false()")
        self.db.get_err_msg = "It's bolted to the facility floor. It isn't going anywhere, and neither are you."


class FacilityBoard(FacilityFurniture):
    """The status board — its description IS the subject's live processing record."""

    def _subject(self):
        # Prefer the explicitly-assigned subject; else any facility subject here.
        from evennia import search_object
        sid = self.db.subject_id
        if sid:
            res = search_object(f"#{sid}")
            if res:
                return res[0]
        room = self.location
        if room:
            for o in room.contents:
                if getattr(o.db, "facility_active", False):
                    return o
        return None

    def get_display_desc(self, looker, **kwargs):
        subj = self._subject()
        if not subj:
            return ("A vast board on the wall, chalked and re-chalked — blank just now, "
                    "waiting for a resident to grade.")
        try:
            from commands.facility_commands import build_board_text
            return build_board_text(subj)
        except Exception:
            return "A vast status board, its figures smeared beyond reading."


class FacilityPortfolio(FacilityFurniture):
    """The Marking Parlour's portfolio — a real, readable catalogue of every piece
    the parlour has set, grouped by owner. `process <unit> portfolio` appends an
    entry; `look`/`read portfolio` pages through it."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.entries = []   # list of {owner, subject, mark, date}

    def add_entry(self, owner, subject, mark):
        import time
        entries = list(self.db.entries or [])
        entries.append({
            "owner":   owner or "the facility",
            "subject": subject or "a unit",
            "mark":    mark or "marked",
            "date":    time.strftime("%Y-%m-%d", time.localtime()),
        })
        # Keep it from growing without bound; the most recent 200 pieces.
        self.db.entries = entries[-200:]

    def get_display_desc(self, looker, **kwargs):
        entries = list(self.db.entries or [])
        head = ("|wThe Parlour Portfolio|n — framed photographs and cured hide-prints, "
                "catalogued by owner. Every piece the parlour has set, kept on record.\n"
                "|x" + "─" * 50 + "|n")
        if not entries:
            return head + "\n  The album is new — clean pages, waiting for a first piece."
        # Group by owner.
        by_owner = {}
        for e in entries:
            by_owner.setdefault(e.get("owner", "the facility"), []).append(e)
        lines = [head]
        for owner in sorted(by_owner):
            page = by_owner[owner]
            lines.append(f"\n|wPage — {owner}|n  ({len(page)} piece(s))")
            for e in page[-12:]:
                lines.append(f"  |x{e.get('date','')}|n  {e.get('subject','a unit')}: "
                             f"{e.get('mark','marked')}")
        lines.append("\n|x" + "─" * 50 + "|n")
        lines.append(f"|x{len(entries)} piece(s) on record across {len(by_owner)} owner(s). "
                     "Nothing in here ever comes off the body, or out of the book.|n")
        return "\n".join(lines)
