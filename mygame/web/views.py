"""
Custom web views for Re:Void.

Uses Django's TemplateView directly rather than subclassing Evennia's IndexView,
so we're not tied to Evennia's internal module structure.

Evennia's context processors already inject: account, puppet, webclient_enabled,
register_enabled, rest_api_enabled into every template automatically.
We just add the homepage-specific stats and news posts here.
"""

from django.views.generic import TemplateView, View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.shortcuts import redirect
from django.contrib import messages
from evennia.objects.models import ObjectDB
from django.conf import settings


class ReVoidIndexView(TemplateView):
    template_name = "website/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # --- Players currently online ---
        try:
            from evennia import SESSION_HANDLER
            sessions = SESSION_HANDLER.get_sessions()
            connected_accounts = set()
            for sess in sessions:
                if sess.account:
                    connected_accounts.add(sess.account.pk)
            context["num_accounts_connected"] = len(connected_accounts)
        except Exception:
            context["num_accounts_connected"] = 0

        # --- Total characters ---
        try:
            char_path = settings.BASE_CHARACTER_TYPECLASS
            context["num_characters"] = ObjectDB.objects.filter(
                db_typeclass_path=char_path
            ).count()
        except Exception:
            context["num_characters"] = 0

        # --- Total rooms ---
        try:
            room_path = settings.BASE_ROOM_TYPECLASS
            context["num_rooms"] = ObjectDB.objects.filter(
                db_typeclass_path=room_path
            ).count()
        except Exception:
            context["num_rooms"] = 0

        # --- News posts ---
        try:
            from web.news.models import NewsPost
            context["news_posts"] = NewsPost.objects.filter(published=True)[:6]
        except Exception:
            context["news_posts"] = []

        return context


# ---------------------------------------------------------------------------
# Zone / Wardrobe web editor
# ---------------------------------------------------------------------------

# Grouped zone display order — mirrors ZONE_GROUPS in typeclasses/characters.py
_ZONE_GROUPS = [
    ("Head",        ["hair", "face", "eyes", "lips", "ears"]),
    ("Neck",        ["throat", "neck", "nape"]),
    ("Upper Torso", ["shoulders", "chest", "back"]),
    ("Arms",        ["arms", "wrists", "hands"]),
    ("Core",        ["abdomen", "waist", "hips", "lower_back"]),
    ("Lower Body",  ["thighs", "legs", "ankles", "feet"]),
]


def _ordered_zone_names(zones_dict):
    """
    Return zone names in a logical display order (default zones first,
    in anatomical order, then freeform zones alphabetically).
    """
    ordered = []
    seen = set()
    for _group, zone_names in _ZONE_GROUPS:
        for name in zone_names:
            if name in zones_dict and name not in seen:
                ordered.append(name)
                seen.add(name)
    # Freeform zones after
    for name in sorted(zones_dict.keys()):
        if name not in seen:
            ordered.append(name)
    return ordered


@method_decorator(login_required, name="dispatch")
class WardrobeView(View):
    """
    Zone / wardrobe web editor.

    GET  /profile/wardrobe/?char=<pk>&zone=<name>
         Renders the editor with the selected character and zone pre-loaded.
         Defaults to the account's first character and first zone.

    POST /profile/wardrobe/
         Saves the nude description for a single zone and redirects back.
    """

    template_name = "website/wardrobe.html"

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    def _get_characters(self, account):
        """Return all Character objects owned by this account."""
        try:
            return list(account.characters.all())
        except Exception:
            return []

    def _get_character(self, account, char_pk):
        """Return a character owned by this account by pk, or None."""
        chars = self._get_characters(account)
        for c in chars:
            if str(c.pk) == str(char_pk):
                return c
        return chars[0] if chars else None

    # ------------------------------------------------------------------ #
    # GET
    # ------------------------------------------------------------------ #

    def get(self, request):
        from django.shortcuts import render
        account = request.user
        chars = self._get_characters(account)

        if not chars:
            return render(request, self.template_name, {
                "chars": [],
                "selected_char": None,
                "zones": [],
                "selected_zone": None,
                "zone_content": "",
                "success": False,
            })

        # Resolve selected character
        char_pk = request.GET.get("char", "")
        selected_char = self._get_character(account, char_pk) if char_pk else chars[0]

        # Resolve zones
        zones_dict = selected_char.db.zones or {}
        zone_names = _ordered_zone_names(zones_dict)

        # Resolve selected zone
        zone_name = request.GET.get("zone", "")
        if zone_name not in zones_dict:
            zone_name = zone_names[0] if zone_names else ""

        # Selected zone data
        zone_data = zones_dict.get(zone_name, {}) if zone_name else {}
        zone_content    = zone_data.get("nude", "") or ""
        zone_visibility = zone_data.get("visibility", "look")
        zone_type       = zone_data.get("zone_type", "surface")
        zone_intimate   = zone_data.get("intimate", False)
        zone_consent    = zone_data.get("consent_required", "casual")

        # Build zone list with display info for the dropdown
        zone_display = []
        for zn in zone_names:
            z = zones_dict[zn]
            has_desc = bool((z.get("nude") or "").strip())
            zone_display.append({
                "name": zn,
                "label": zn.replace("_", " ").title(),
                "has_desc": has_desc,
                "intimate": z.get("intimate", False),
            })

        # Freeform items on the selected zone
        all_freeform = selected_char.db.freeform_items or {}
        zone_freeform = []
        for iname, idata in sorted(all_freeform.items()):
            if idata.get("zone") != zone_name:
                continue
            lock      = idata.get("lock")
            lock_info = None
            if lock:
                ltype = lock.get("type", "?")
                if ltype == "plock":
                    key_id     = lock.get("key_id")
                    holder_name = None
                    if key_id:
                        try:
                            from evennia.objects.models import ObjectDB
                            key_obj = ObjectDB.objects.get(pk=key_id)
                            loc = key_obj.db_location
                            if loc:
                                holder_name = (
                                    getattr(loc, 'db', None) and
                                    (loc.db.rp_name or loc.key)
                                ) or str(loc)
                        except Exception:
                            pass
                    lock_info = {
                        "type":        "plock",
                        "key_id":      key_id,
                        "holder_name": holder_name or "unknown",
                    }
                else:
                    lock_info = {
                        "type":  "slock",
                        "code":  lock.get("code", "?"),
                    }
            zone_freeform.append({
                "name":        iname,
                "desc":        idata.get("desc", ""),
                "player_desc": idata.get("player_desc", ""),
                "mode":        idata.get("display_mode", "on"),
                "lock":        lock_info,
                "placed_by_id": idata.get("placed_by"),
            })

        return render(request, self.template_name, {
            "chars": chars,
            "selected_char": selected_char,
            "zone_display": zone_display,
            "selected_zone": zone_name,
            "zone_content": zone_content,
            "zone_visibility": zone_visibility,
            "zone_type":       zone_type,
            "zone_intimate":   zone_intimate,
            "zone_consent":    zone_consent,
            "zone_freeform":   zone_freeform,
            "success": request.GET.get("saved") == "1",
            # Choices for dropdowns
            "visibility_choices": [
                ("look",      "Look — visible on standard look"),
                ("examine",   "Examine — visible on examine"),
                ("deep",      "Deep — examine closely only"),
                ("proximity", "Proximity — near/with only"),
                ("consent",   "Consent — requires consent flag"),
                ("hidden",    "Hidden — private, not shown"),
            ],
            "type_choices": [
                ("surface",    "Surface — things rest on or against it"),
                ("orifice",    "Orifice — things can be placed inside"),
                ("both",       "Both — surface and orifice"),
                ("attachment", "Attachment — things attach or pierce"),
            ],
            "consent_choices": [
                ("casual",   "Casual — open interaction"),
                ("intimate", "Intimate — personal contact"),
                ("mature",   "Mature — adult content"),
                ("bdsm",     "BDSM — explicit consent required"),
            ],
        })

    # ------------------------------------------------------------------ #
    # POST — save a zone description
    # ------------------------------------------------------------------ #

    def post(self, request):
        account   = request.user
        char_pk   = request.POST.get("char_id", "")
        action    = request.POST.get("action", "save_zone")
        zone_name = request.POST.get("zone_name", "").strip().lower().replace(" ", "_")

        selected_char = self._get_character(account, char_pk)
        if not selected_char:
            messages.error(request, "Character not found.")
            return redirect("/profile/wardrobe/")

        # ── Save freeform item player_desc ────────────────────────────────
        if action == "save_item_desc":
            item_name   = request.POST.get("item_name", "").strip().lower()
            player_desc = request.POST.get("player_desc", "").strip()

            items = selected_char.db.freeform_items or {}
            if item_name not in items:
                messages.error(request, f"Item '{item_name}' not found.")
                return redirect(f"/profile/wardrobe/?char={char_pk}&zone={zone_name}")

            items[item_name]["player_desc"] = player_desc
            selected_char.db.freeform_items = items
            return redirect(
                f"/profile/wardrobe/?char={char_pk}&zone={zone_name}&saved=1"
            )

        # ── Save zone nude desc + flags (default action) ──────────────────
        nude_desc = request.POST.get("nude_desc", "").strip()

        # Flag fields
        _VALID_VISIBILITY = {"look", "examine", "deep", "proximity", "consent", "hidden"}
        _VALID_TYPES      = {"surface", "orifice", "both", "attachment"}
        _VALID_CONSENT    = {"casual", "intimate", "mature", "bdsm"}

        visibility = request.POST.get("visibility", "look")
        zone_type  = request.POST.get("zone_type", "surface")
        intimate   = request.POST.get("intimate") == "1"
        consent    = request.POST.get("consent_required", "casual")

        # Sanitise — ignore anything not in the valid sets
        if visibility not in _VALID_VISIBILITY: visibility = "look"
        if zone_type  not in _VALID_TYPES:      zone_type  = "surface"
        if consent    not in _VALID_CONSENT:    consent    = "casual"

        zones_dict = selected_char.db.zones or {}

        if zone_name not in zones_dict:
            messages.error(request, f"Zone '{zone_name}' not found on this character.")
            return redirect(f"/profile/wardrobe/?char={char_pk}&zone={zone_name}")

        # Apply all changes
        zones_dict[zone_name]["nude"]             = nude_desc
        zones_dict[zone_name]["visibility"]       = visibility
        zones_dict[zone_name]["zone_type"]        = zone_type
        zones_dict[zone_name]["intimate"]         = intimate
        zones_dict[zone_name]["consent_required"] = consent

        # Write the whole dict back so Evennia persists it
        selected_char.db.zones = zones_dict

        return redirect(f"/profile/wardrobe/?char={char_pk}&zone={zone_name}&saved=1")
