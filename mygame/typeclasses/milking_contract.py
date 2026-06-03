"""
typeclasses/milking_contract.py

MilkingContract — a written contract item with visible and hidden clauses.

Structure:
  - Visible clauses: text the signee can read before signing
  - Hidden clauses: text only revealed when the author chooses, or auto-revealed
                    on specific triggers (signing, time elapsed, event)
  - Addendums: additional clauses added after initial signing, may be hidden

When signed, the contract's effects activate on the signee:
  - Duration (hours) of arousal_floor + continuous_stimulation
  - Binding effects from hidden clauses activate silently on signing

The "scummy" angle: the author shows the signee a clean contract with
reasonable visible clauses. Hidden clauses carry the actual binding effects.
When revealed (manually or on a trigger), the signee sees what they agreed to.

Commands:
  contract read <contract>                — read visible text
  contract read/all <contract>            — read everything (author only)
  contract sign <contract>                — sign and activate effects
  contract addend <contract> = <text>     — add a visible addendum
  contract addend/hidden <contract> = <text> — add a hidden addendum
  contract reveal <contract> [clause_id]  — reveal a hidden clause to everyone
  contract reveal/all <contract>          — reveal all hidden clauses
  contract status <contract>              — show signing status, active effects
"""

import time
from typeclasses.written_item import WrittenItem


class MilkingContract(WrittenItem):
    """
    A contract item with visible and hidden clauses.

    The signee sees only visible_clauses until the author reveals hidden ones.
    """

    def at_object_creation(self):
        super().at_object_creation() if hasattr(super(), "at_object_creation") else None
        try:
            super().at_object_creation()
        except Exception:
            from evennia import DefaultObject
            DefaultObject.at_object_creation(self)

        self.key              = "contract"
        self.db.desc          = "A formal document, sealed and signed."
        self.db.author_id     = None     # character id of the author
        self.db.signee_id     = None     # character id who signed
        self.db.signed        = False
        self.db.signed_at     = None     # unix timestamp

        # Clauses — list of {id, text, hidden, revealed, added_at}
        self.db.clauses        = []
        self.db.addendums      = []

        # Effects that activate on signing
        self.db.duration_hours       = 24.0
        self.db.effect_arousal_floor = 0.0
        self.db.effect_stim_per_tick = 0.0
        self.db.binding_effects      = {}   # hidden binding effects

        # If True, all hidden clauses are revealed to the signee the instant
        # they sign — and the full text is dropped on them. The classic payoff:
        # you find out what you agreed to only once it's already binding.
        self.db.reveal_on_sign       = False

        self.db.player_desc  = ""
        self.db.desc_locked  = False

    # ------------------------------------------------------------------
    # Clause management
    # ------------------------------------------------------------------

    def add_clause(self, text: str, hidden: bool = False) -> int:
        """Add a clause. Returns its ID."""
        clauses = list(self.db.clauses or [])
        clause_id = len(clauses) + 1
        clauses.append({
            "id":       clause_id,
            "text":     text,
            "hidden":   hidden,
            "revealed": False,
            "added_at": time.time(),
        })
        self.db.clauses = clauses
        return clause_id

    def add_addendum(self, text: str, hidden: bool = False) -> int:
        """Add an addendum. Returns its ID."""
        adds = list(self.db.addendums or [])
        add_id = len(adds) + 1
        adds.append({
            "id":       add_id,
            "text":     text,
            "hidden":   hidden,
            "revealed": False,
            "added_at": time.time(),
        })
        self.db.addendums = adds
        return add_id

    def reveal_clause(self, clause_id: int = None, all_hidden: bool = False):
        """
        Reveal a hidden clause (or all) to the signee and anyone who can see.
        clause_id=None + all_hidden=False reveals nothing new.
        """
        clauses = list(self.db.clauses or [])
        changed = []
        for clause in clauses:
            if not clause.get("hidden") or clause.get("revealed"):
                continue
            if all_hidden or clause.get("id") == clause_id:
                clause["revealed"] = True
                changed.append(clause)
        self.db.clauses = clauses

        addendums = list(self.db.addendums or [])
        for add in addendums:
            if not add.get("hidden") or add.get("revealed"):
                continue
            if all_hidden or add.get("id") == clause_id:
                add["revealed"] = True
                changed.append(add)
        self.db.addendums = addendums

        return changed

    def get_visible_text(self, include_hidden: bool = False) -> str:
        """Build the full visible contract text."""
        lines = []
        lines.append(f"|w{self.key.upper()}|n")
        lines.append("|w" + "─" * 44 + "|n")

        clauses = self.db.clauses or []
        for c in clauses:
            if c.get("hidden") and not c.get("revealed") and not include_hidden:
                continue
            prefix = "|r[HIDDEN — now revealed]|n " if (c.get("hidden") and c.get("revealed") and not include_hidden) else ""
            prefix += "|y[HIDDEN]|n " if (c.get("hidden") and include_hidden and not c.get("revealed")) else ""
            lines.append(f"{prefix}{c.get('text', '')}")

        addendums = self.db.addendums or []
        if addendums:
            lines.append("\n|wAddendums:|n")
            for a in addendums:
                if a.get("hidden") and not a.get("revealed") and not include_hidden:
                    continue
                prefix = "|r[ADDENDUM — now revealed]|n " if (a.get("hidden") and a.get("revealed") and not include_hidden) else ""
                prefix += "|y[HIDDEN ADDENDUM]|n " if (a.get("hidden") and include_hidden and not a.get("revealed")) else ""
                lines.append(f"{prefix}{a.get('text', '')}")

        # Signing status
        if self.db.signed:
            from evennia.objects.models import ObjectDB
            try:
                signee = ObjectDB.objects.get(pk=self.db.signee_id)
                sname  = signee.db.rp_name or signee.key
            except Exception:
                sname = f"#{self.db.signee_id}"
            signed_at = self.db.signed_at or 0
            import datetime
            dt = datetime.datetime.fromtimestamp(signed_at).strftime("%Y-%m-%d %H:%M")
            lines.append(f"\n|xSigned by {sname} at {dt}.|n")
        else:
            lines.append("\n|x[Unsigned]|n")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def sign(self, signee) -> tuple:
        """
        Signee signs the contract and all effects activate.
        Returns (True, "") or (False, reason).
        """
        if self.db.signed:
            return False, "This contract has already been signed."

        self.db.signed     = True
        self.db.signee_id  = signee.id
        self.db.signed_at  = time.time()

        # Apply duration-based effects
        duration = float(self.db.duration_hours or 24.0)
        floor    = float(self.db.effect_arousal_floor or 0.0)
        stim     = float(self.db.effect_stim_per_tick or 0.0)
        expires  = time.time() + duration * 3600

        if floor > 0 or stim > 0:
            signee.db.arousal_floor = max(
                float(signee.db.arousal_floor or 0.0), floor
            )
            signee.db.stim_per_tick = float(signee.db.stim_per_tick or 0.0) + stim
            expirations = list(signee.db.aphrodisiac_expirations or [])
            expirations.append({
                "expires": expires,
                "floor":   floor,
                "stim":    stim,
            })
            signee.db.aphrodisiac_expirations = expirations

        # Apply hidden binding effects silently
        if self.db.binding_effects:
            try:
                from world.binding_effects import apply_effects
                apply_effects(signee, self)
            except Exception:
                pass

        # Auto-reveal the hidden clauses to the signee — they can read what they
        # agreed to, now that agreeing is done. Drop the full text on them.
        if self.db.reveal_on_sign:
            self.reveal_clause(all_hidden=True)
            try:
                signee.msg(
                    "\n|rThe pages turn face-up. Here is what you just agreed to:|n\n"
                    + self.get_visible_text()
                )
            except Exception:
                pass

        return True, ""


# ---------------------------------------------------------------------------
# CmdContract — read, sign, addend, reveal
# ---------------------------------------------------------------------------

from evennia.commands.default.muxcommand import MuxCommand


class CmdContract(MuxCommand):
    """
    Interact with a milking contract.

    Usage:
      contract read <contract>                  — read visible clauses
      contract read/all <contract>              — read all clauses (author only)
      contract sign <contract>                  — sign and activate effects
      contract addend <contract> = <text>       — add visible addendum
      contract addend/hidden <contract> = <text>— add hidden addendum
      contract reveal <contract> [clause_id]    — reveal a hidden clause
      contract reveal/all <contract>            — reveal all hidden clauses
      contract status <contract>                — show signing status
    """

    key     = "contract"
    locks   = "cmd:all()"
    help_category = "Items"
    switch_options = ("read", "sign", "addend", "reveal", "status", "all", "hidden")

    def func(self):
        caller   = self.caller
        args     = self.args.strip()
        switches = list(self.switches)

        # Accept the action as a leading word too, so both 'contract/read X' and
        # 'contract read X' work. (The docstring promises the second form.)
        _actions = ("read", "sign", "addend", "reveal", "status")
        parts = args.split(None, 1)
        if parts and parts[0].lower() in _actions and parts[0].lower() not in switches:
            switches.append(parts[0].lower())
            args = parts[1].strip() if len(parts) > 1 else ""
            # also fold a trailing 'all'/'hidden' qualifier: 'read all contract'
            sub = args.split(None, 1)
            if sub and sub[0].lower() in ("all", "hidden"):
                switches.append(sub[0].lower())
                args = sub[1].strip() if len(sub) > 1 else ""

        if "read" in switches:
            self._do_read(caller, args, include_hidden="all" in switches)
        elif "sign" in switches:
            self._do_sign(caller, args)
        elif "addend" in switches:
            self._do_addend(caller, args, hidden="hidden" in switches)
        elif "reveal" in switches:
            self._do_reveal(caller, args, all_hidden="all" in switches)
        elif "status" in switches:
            self._do_status(caller, args)
        else:
            caller.msg(
                "|xUsage: contract read/sign/addend/reveal/status <contract>|n"
            )

    def _find_contract(self, caller, name):
        from typeclasses.milking_contract import MilkingContract
        # Search inventory AND the current room (the contract is often set in
        # front of the signee rather than handed to them).
        candidates = list(caller.contents)
        if caller.location:
            candidates += list(caller.location.contents)
        contracts = [o for o in candidates if isinstance(o, MilkingContract)]
        if not contracts:
            caller.msg(f"|xThere's no contract here to {name and 'read' or 'use'}.|n"
                       if False else "|xThere's no contract here.|n")
            return None
        # If a name was given, prefer a key/alias match; else take the first.
        if name:
            named = [o for o in contracts
                     if name.lower() in (o.key or "").lower()
                     or name.lower() in [a.lower() for a in (o.aliases.all() or [])]]
            if named:
                return named[0]
        return contracts[0]

    def _is_author(self, caller, contract):
        return (
            caller.is_superuser or
            caller.check_permstring("Admin") or
            contract.db.author_id == caller.id
        )

    def _do_read(self, caller, args, include_hidden=False):
        contract = self._find_contract(caller, args)
        if not contract:
            return
        if include_hidden and not self._is_author(caller, contract):
            caller.msg("|xOnly the author can read hidden clauses.|n")
            include_hidden = False
        caller.msg(contract.get_visible_text(include_hidden=include_hidden))

    def _do_sign(self, caller, args):
        contract = self._find_contract(caller, args)
        if not contract:
            return
        ok, reason = contract.sign(caller)
        if not ok:
            caller.msg(f"|x{reason}|n")
            return
        caller.msg("|wYou sign the contract. The terms are now in effect.|n")
        room = caller.location
        if room:
            cname = caller.db.rp_name or caller.name
            room.msg_contents(
                f"|x{cname} signs a contract.|n", exclude=[caller]
            )

    def _do_addend(self, caller, args, hidden=False):
        if "=" not in args:
            caller.msg("|xUsage: contract addend <contract> = <text>|n")
            return
        name, _, text = args.partition("=")
        contract = self._find_contract(caller, name.strip())
        if not contract:
            return
        if not self._is_author(caller, contract):
            caller.msg("|xOnly the author can add clauses.|n")
            return
        add_id = contract.add_addendum(text.strip(), hidden=hidden)
        tag = " (hidden)" if hidden else ""
        caller.msg(f"|wAddendum #{add_id} added{tag}.|n")

    def _do_reveal(self, caller, args, all_hidden=False):
        parts = args.split(None, 1)
        name  = parts[0]
        clause_id = None
        if len(parts) > 1:
            try:
                clause_id = int(parts[1])
            except ValueError:
                pass
        contract = self._find_contract(caller, name)
        if not contract:
            return
        if not self._is_author(caller, contract):
            caller.msg("|xOnly the author can reveal hidden clauses.|n")
            return
        revealed = contract.reveal_clause(clause_id=clause_id, all_hidden=all_hidden)
        if not revealed:
            caller.msg("|xNo hidden clauses to reveal.|n")
            return

        # Notify the signee if present
        room = caller.location
        if room and contract.db.signee_id:
            from evennia import search_object
            results = search_object(f"#{contract.db.signee_id}", exact=True)
            if results and results[0].location == room:
                results[0].msg(
                    f"|r{caller.db.rp_name or caller.name} reveals "
                    f"{len(revealed)} hidden clause(s) in the contract you signed.|n"
                )
        caller.msg(f"|w{len(revealed)} clause(s) revealed.|n")

    def _do_status(self, caller, args):
        contract = self._find_contract(caller, args)
        if not contract:
            return
        signed = contract.db.signed
        if signed:
            from evennia.objects.models import ObjectDB
            try:
                s = ObjectDB.objects.get(pk=contract.db.signee_id)
                sname = s.db.rp_name or s.key
            except Exception:
                sname = f"#{contract.db.signee_id}"
        else:
            sname = "—"
        hidden_count = sum(
            1 for c in (contract.db.clauses or [])
            if c.get("hidden") and not c.get("revealed")
        )
        caller.msg(
            f"|w{contract.key}|n\n"
            f"  Signed:         {'yes' if signed else 'no'}  ({sname})\n"
            f"  Clauses:        {len(contract.db.clauses or [])}\n"
            f"  Hidden (unrevealed): {hidden_count}\n"
            f"  Addendums:      {len(contract.db.addendums or [])}\n"
            f"  Duration:       {contract.db.duration_hours}h\n"
            f"  Effects on sign: floor={contract.db.effect_arousal_floor} "
            f"stim={contract.db.effect_stim_per_tick}"
        )


ALL_CONTRACT_CMDS = [CmdContract]
