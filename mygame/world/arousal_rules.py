"""
world/arousal_rules.py — one resolver for "may she come right now, and is it permitted".

Three flags used to be set/read independently across arousal_script, compliance, rules,
conditioning, star_chart and the facility command set, which produced the recurring
"permitted but still capped at 99" / "granted release still punished by ask_to_come"
bugs. This is the single source of truth:

  * `orgasm_denial`         — denial is in force (arousal caps at 99, can't climax)
  * `orgasm_denial_lifted`  — a one-shot lift of that cap (lets ONE climax through)
  * `rule_come_permit`      — a one-shot permission so the ask_to_come RULE doesn't punish
                              the release that happens

`grant_release()` is the ONE way to permit a climax — it sets BOTH one-shots together, so a
granted release both reaches 100 AND isn't punished. The §0 floor clears all three flags.
"""


def is_denied(character):
    return bool(getattr(character.db, "orgasm_denial", False))


def cap_for(character):
    """The arousal cap right now: 100 if she may climax, else 99 (held on the edge)."""
    if not is_denied(character) or getattr(character.db, "orgasm_denial_lifted", False):
        return 100.0
    return 99.0


def may_climax(character):
    """True if a climax is allowed to fire right now (not denied, or denial one-shot-lifted)."""
    return (not is_denied(character)) or bool(getattr(character.db, "orgasm_denial_lifted", False))


def grant_release(character):
    """The single canonical way to PERMIT one climax: lift the cap AND set the rule permit,
    so the granted release both reaches 100 and isn't punished by ask_to_come. One-shot —
    both are consumed when the climax fires (see consume_release + conditioning.deepen_on_climax)."""
    if not character:
        return
    character.db.orgasm_denial_lifted = True
    character.db.rule_come_permit = True


def consume_release(character):
    """Spend the one-shot cap lift when a permitted climax fires. (The rule permit is consumed
    separately by conditioning.deepen_on_climax via rules.enforce.)"""
    if getattr(character.db, "orgasm_denial_lifted", False):
        character.db.orgasm_denial_lifted = False
