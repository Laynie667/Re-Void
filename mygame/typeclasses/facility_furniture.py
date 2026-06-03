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
