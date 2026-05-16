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

    # Preferred root and child display orders (mirrors characters.py)
    _ROOT_ORDER  = ["head", "neck", "torso", "arms", "groin", "legs"]
    _CHILD_ORDER = [
        "hair", "face", "eyes", "lips", "mouth", "tongue", "ears",
        "throat", "nape",
        "shoulders", "chest", "abdomen", "back", "lower_back", "waist",
        "wrists", "hands",
        "hips", "thighs", "ankles", "feet",
    ]

    @staticmethod
    def _plain(obj):
        """Recursively convert Evennia _SaverDict/_SaverList proxies to plain Python.
        Uses duck-typing (hasattr) rather than isinstance so it works regardless of
        whether _SaverDict subclasses dict in the installed Evennia version."""
        if hasattr(obj, 'items'):                          # dict or _SaverDict
            return {k: WardrobeView._plain(v) for k, v in obj.items()}
        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):  # list/_SaverList
            return [WardrobeView._plain(i) for i in obj]
        return obj

    @staticmethod
    def _build_zone_order(zones_dict):
        """
        Return zone names in depth-first tree order from a plain Python dict.
        Guaranteed to work on plain dicts — no _SaverDict dependency.
        """
        _root_order  = WardrobeView._ROOT_ORDER
        _child_order = WardrobeView._CHILD_ORDER

        children_map = {}
        roots = []
        for name, zdata in zones_dict.items():
            parent = zdata.get("parent") if isinstance(zdata, dict) else None
            if parent and parent in zones_dict:
                children_map.setdefault(parent, []).append(name)
            else:
                roots.append(name)

        def _sort(names, preferred):
            idx = {n: i for i, n in enumerate(preferred)}
            return sorted(names, key=lambda z: (idx.get(z, len(preferred)), z))

        for p in list(children_map):
            children_map[p] = _sort(children_map[p], _child_order)

        ordered_roots = _sort(roots, _root_order)

        result = []
        seen = set()

        def _walk(name):
            if name in seen:
                return
            seen.add(name)
            result.append(name)
            for child in children_map.get(name, []):
                _walk(child)

        for root in ordered_roots:
            _walk(root)

        # Safety net for any zone somehow not reached
        for name in sorted(zones_dict):
            if name not in seen:
                result.append(name)

        return result

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

        # Strip _SaverDict/_SaverList proxies before ANY tree logic so that
        # dict.get() and "key in dict" behave as plain Python everywhere.
        zones_dict = self._plain(selected_char.db.zones or {})
        zone_names = self._build_zone_order(zones_dict)

        # Resolve selected zone
        zone_name = request.GET.get("zone", "")
        if zone_name not in zones_dict:
            zone_name = zone_names[0] if zone_names else ""

        # Selected zone data
        zone_data = zones_dict.get(zone_name, {}) if zone_name else {}
        zone_content    = zone_data.get("nude", "") or ""
        zone_interior   = zone_data.get("interior", "") or ""
        zone_visibility = zone_data.get("visibility", "look")
        zone_type       = zone_data.get("zone_type", "surface")
        zone_intimate   = zone_data.get("intimate", False)
        zone_consent    = zone_data.get("consent_required", "casual")
        zone_parent     = zone_data.get("parent") or ""
        # covered_by is a dict with worn_desc/examine_desc/state, or None
        _raw_covered    = zone_data.get("covered_by")
        zone_covered    = dict(_raw_covered) if isinstance(_raw_covered, dict) else None

        def _zone_depth(name, zdict, _seen=None):
            """Walk parent chain to calculate depth (0 = root)."""
            if _seen is None:
                _seen = set()
            if name in _seen:
                return 0
            _seen.add(name)
            p = zdict.get(name, {}).get("parent")
            if not p or p not in zdict:
                return 0
            return 1 + _zone_depth(p, zdict, _seen)

        # Build zone list with display info for the dropdown
        zone_display = []
        for zn in zone_names:
            z = zones_dict[zn]
            depth = _zone_depth(zn, zones_dict)
            has_desc = bool((z.get("nude") or "").strip())
            has_interior = bool((z.get("interior") or "").strip())
            zone_display.append({
                "name":         zn,
                "label":        zn.replace("_", " ").title(),
                "has_desc":     has_desc,
                "has_interior": has_interior,
                "intimate":     z.get("intimate", False),
                "zone_type":    z.get("zone_type", "surface"),
                "parent":       z.get("parent") or "",
                "depth":        depth,
                "indent":       "—" * depth,
            })

        # Build accordion: independent DFS walk — does NOT rely on zone_display order.
        # Works directly from zones_dict (already plain Python), so ordering is
        # determined entirely by _CHILD_ORDER / _ROOT_ORDER, not dict iteration order.
        _child_pref = {n: i for i, n in enumerate(WardrobeView._CHILD_ORDER)}
        _root_pref  = {n: i for i, n in enumerate(WardrobeView._ROOT_ORDER)}

        def _acc_children(parent, depth=1):
            """Return all descendants of `parent` in preferred DFS order."""
            kids = [
                (name, data)
                for name, data in zones_dict.items()
                if hasattr(data, 'items') and data.get("parent") == parent
            ]
            kids.sort(key=lambda nd: (_child_pref.get(nd[0], 999), nd[0]))
            out = []
            for name, data in kids:
                out.append({
                    "name":         name,
                    "label":        name.replace("_", " ").title(),
                    "has_desc":     bool((data.get("nude") or "").strip()),
                    "has_interior": bool((data.get("interior") or "").strip()),
                    "intimate":     data.get("intimate", False),
                    "zone_type":    data.get("zone_type", "surface"),
                    "parent":       data.get("parent") or "",
                    "depth":        depth,
                })
                out.extend(_acc_children(name, depth + 1))
            return out

        # Identify root zones (no parent, or parent not present in the dict)
        root_items = [
            (name, data)
            for name, data in zones_dict.items()
            if not (
                hasattr(data, 'items')
                and data.get("parent")
                and data.get("parent") in zones_dict
            )
        ]
        root_items.sort(key=lambda nd: (_root_pref.get(nd[0], 999), nd[0]))

        zone_accordion = []
        for rname, rdata in root_items:
            descendants = _acc_children(rname)
            zone_accordion.append({
                "name":              rname,
                "label":             rname.replace("_", " ").title(),
                "has_desc":          bool((rdata.get("nude") or "").strip()),
                "has_interior":      bool((rdata.get("interior") or "").strip()),
                "intimate":          rdata.get("intimate", False),
                "zone_type":         rdata.get("zone_type", "surface"),
                "parent":            "",
                "depth":             0,
                "descendants":       descendants,
                "contains_selected": zone_name in {d["name"] for d in descendants},
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
            "zone_accordion": zone_accordion,
            "selected_zone": zone_name,
            "zone_content": zone_content,
            "zone_interior":  zone_interior,
            "zone_visibility": zone_visibility,
            "zone_type":       zone_type,
            "zone_intimate":   zone_intimate,
            "zone_consent":    zone_consent,
            "zone_parent":     zone_parent,
            "zone_covered":    zone_covered,
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
    # POST — all wardrobe mutations
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

        base_url = f"/profile/wardrobe/?char={char_pk}&zone={zone_name}"

        # ── Save freeform item player_desc ────────────────────────────────
        if action == "save_item_desc":
            item_name   = request.POST.get("item_name", "").strip().lower()
            player_desc = request.POST.get("player_desc", "").strip()

            items = self._plain(selected_char.db.freeform_items or {})
            if item_name not in items:
                messages.error(request, f"Item '{item_name}' not found.")
                return redirect(base_url)

            items[item_name]["player_desc"] = player_desc
            selected_char.attributes.add("freeform_items", items)
            return redirect(f"{base_url}&saved=1")

        # ── Save interior description ─────────────────────────────────────
        if action == "save_interior":
            interior_desc = request.POST.get("interior_desc", "").strip()
            ok = selected_char.set_zone_interior(zone_name, interior_desc)
            if not ok:
                messages.error(
                    request,
                    f"Could not save interior description for '{zone_name}'. "
                    "Zone must be orifice or both type."
                )
            return redirect(f"{base_url}&saved=1" if ok else base_url)

        # ── Wear clothing on a zone ───────────────────────────────────────
        if action == "wear_zone":
            worn_desc    = request.POST.get("worn_desc", "").strip()
            examine_desc = request.POST.get("examine_desc", "").strip()
            if not worn_desc:
                messages.error(request, "Clothing description cannot be empty.")
                return redirect(base_url)
            ok = selected_char.place_on_zone(
                zone_name,
                worn_desc,
                worn_desc=worn_desc,
                examine_desc=examine_desc or None,
                set_by=selected_char.id,
            )
            if not ok:
                messages.error(request, f"Could not apply clothing to zone '{zone_name}'.")
            return redirect(f"{base_url}&saved=1" if ok else base_url)

        # ── Remove clothing from a zone ───────────────────────────────────
        if action == "remove_clothing":
            ok = selected_char.remove_from_zone(zone_name)
            if not ok:
                messages.error(request, f"Nothing to remove from '{zone_name}'.")
            return redirect(f"{base_url}&saved=1" if ok else base_url)

        # ── Add freeform item ─────────────────────────────────────────────
        if action == "add_freeform":
            from world.freeform_manager import FreeformManager
            item_name    = request.POST.get("item_name", "").strip().lower().replace(" ", "_")
            item_desc    = request.POST.get("item_desc", "").strip()
            display_mode = request.POST.get("display_mode", "on")
            if display_mode not in ("on", "in", "cover"):
                display_mode = "on"
            if not item_name or not item_desc:
                messages.error(request, "Item name and description are required.")
                return redirect(base_url)
            ok, result = FreeformManager.place_item(
                selected_char, zone_name, item_name, item_desc,
                selected_char.id, display_mode=display_mode,
            )
            if not ok:
                messages.error(request, result)
            return redirect(f"{base_url}&saved=1" if ok else base_url)

        # ── Remove freeform item ──────────────────────────────────────────
        if action == "remove_freeform":
            from world.freeform_manager import FreeformManager
            item_name = request.POST.get("item_name", "").strip().lower()
            ok, result = FreeformManager.remove_item(selected_char, item_name)
            if not ok:
                messages.error(request, result)
            return redirect(f"{base_url}&saved=1" if ok else base_url)

        # ── Save zone nude desc + flags (default action) ──────────────────
        nude_desc = request.POST.get("nude_desc", "").strip()

        _VALID_VISIBILITY = {"look", "examine", "deep", "proximity", "consent", "hidden"}
        _VALID_TYPES      = {"surface", "orifice", "both", "attachment"}
        _VALID_CONSENT    = {"casual", "intimate", "mature", "bdsm"}

        visibility = request.POST.get("visibility", "look")
        zone_type  = request.POST.get("zone_type", "surface")
        intimate   = request.POST.get("intimate") == "1"
        consent    = request.POST.get("consent_required", "casual")

        if visibility not in _VALID_VISIBILITY: visibility = "look"
        if zone_type  not in _VALID_TYPES:      zone_type  = "surface"
        if consent    not in _VALID_CONSENT:    consent    = "casual"

        zones_dict = self._plain(selected_char.db.zones or {})

        if zone_name not in zones_dict:
            messages.error(request, f"Zone '{zone_name}' not found on this character.")
            return redirect(base_url)

        zones_dict[zone_name]["nude"]             = nude_desc
        zones_dict[zone_name]["visibility"]       = visibility
        zones_dict[zone_name]["zone_type"]        = zone_type
        zones_dict[zone_name]["intimate"]         = intimate
        zones_dict[zone_name]["consent_required"] = consent

        selected_char.attributes.add("zones", zones_dict)
        return redirect(f"{base_url}&saved=1")
