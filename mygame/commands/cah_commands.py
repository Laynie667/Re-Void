"""
commands/cah_commands.py

Cards Against Re:Void — full game implementation for Evennia.

Attach CmdCAH to a character cmdset or a room cmdset.
Game state is stored on room.db.cah_game (a plain dict).

Commands:
    cah / cah status   -- show current game state
    cah join           -- join the lobby
    cah start [decks]  -- start the game (initiator or Builder)
    cah hand           -- see your private hand
    cah play <n> [n2]  -- play card(s) from your hand
    cah pick <n>       -- czar picks the winning submission
    cah score          -- public scoreboard
    cah leave          -- leave the game
    cah end            -- end the game (initiator or Builder)
    cah decks          -- list available decks
"""

from evennia import Command
from world.cah_loader import load_decks, list_decks, DEFAULT_DECKS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HAND_SIZE = 7


def _new_game_state():
    """Return a fresh, zeroed-out game state dict."""
    return {
        "active": False,
        "phase": "lobby",
        "players": [],
        "player_names": {},
        "czar_idx": 0,
        "hands": {},
        "scores": {},
        "black_card": None,
        "played_cards": {},
        "black_deck": [],
        "white_deck": [],
        "discard_black": [],
        "discard_white": [],
        "hand_size": HAND_SIZE,
        "decks_loaded": [],
        "initiator_id": None,
        "round": 0,
    }


def _draw_black(game):
    """
    Pop one black card from black_deck.
    If the deck is empty, reshuffle discard_black back in.
    Returns the card dict or None if no cards remain at all.
    """
    import random
    if not game["black_deck"]:
        if game["discard_black"]:
            game["black_deck"] = game["discard_black"][:]
            game["discard_black"] = []
            random.shuffle(game["black_deck"])
        else:
            return None
    return game["black_deck"].pop()


def _draw_whites(game, n):
    """
    Draw n white cards from white_deck.
    Reshuffles discard_white if needed.
    Returns a list of up to n card strings.
    """
    import random
    drawn = []
    for _ in range(n):
        if not game["white_deck"]:
            if game["discard_white"]:
                game["white_deck"] = game["discard_white"][:]
                game["discard_white"] = []
                random.shuffle(game["white_deck"])
            else:
                break  # Truly out of cards
        drawn.append(game["white_deck"].pop())
    return drawn


def _deal_hand(game, player_id, count=None):
    """
    Fill a player's hand up to hand_size (or draw `count` cards if specified).
    Modifies game in place.
    """
    if count is None:
        count = game["hand_size"] - len(game["hands"].get(player_id, []))
    if count <= 0:
        return
    if player_id not in game["hands"]:
        game["hands"][player_id] = []
    new_cards = _draw_whites(game, count)
    game["hands"][player_id].extend(new_cards)


def _format_black_card(card):
    """Return a nicely formatted black card string for room display."""
    pick_note = f" |x[Pick {card['pick']}]|n" if card["pick"] > 1 else ""
    return f"|[030|w {card['text']} |n{pick_note}"


def _show_submissions(room, game):
    """
    Display all played submissions to the room, anonymized (numbered, no names).
    Called after all non-czar players have submitted.
    """
    czar_id = game["players"][game["czar_idx"]]
    czar_name = game["player_names"].get(czar_id, "???")
    room.msg_contents(
        f"\n|xAll submissions are in. |y{czar_name}|x, pick the winner!|n\n"
    )
    for idx, pid in enumerate(game["players"]):
        if pid == czar_id:
            continue
        cards = game["played_cards"].get(pid)
        if not cards:
            continue
        card_display = "  |w" + "|n  /  |w".join(cards) + "|n"
        room.msg_contents(f"  |x[{idx + 1}]|n\n{card_display}\n")


def _next_round(room, game):
    """
    Advance to the next round:
    - Discard played white cards and current black card
    - Refill all players' hands
    - Rotate czar
    - Draw a new black card
    - Reset played_cards
    """
    # Discard played white cards
    for pid, cards in game["played_cards"].items():
        game["discard_white"].extend(cards)
    game["played_cards"] = {}

    # Discard current black card
    if game["black_card"]:
        game["discard_black"].append(game["black_card"])
        game["black_card"] = None

    # Refill hands
    for pid in game["players"]:
        _deal_hand(game, pid)

    # Rotate czar
    game["czar_idx"] = (game["czar_idx"] + 1) % len(game["players"])
    game["round"] += 1

    # Draw new black card
    new_black = _draw_black(game)
    if new_black is None:
        room.msg_contents(
            "|rThe black card deck is completely exhausted. The game is over.|n"
        )
        game["active"] = False
        game["phase"] = "lobby"
        return

    game["black_card"] = new_black
    game["phase"] = "playing"

    czar_id = game["players"][game["czar_idx"]]
    czar_name = game["player_names"].get(czar_id, "???")

    room.msg_contents(
        f"\n|x--- Round {game['round']} ---\n"
        f"Card Czar: |y{czar_name}|n\n\n"
        f"{_format_black_card(new_black)}\n\n"
        f"|x{czar_name} waits while everyone else plays their cards.|n\n"
    )


def _get_or_create_game(room):
    """Return the game state dict, creating it fresh if it doesn't exist."""
    if not room.db.cah_game:
        room.db.cah_game = _new_game_state()
    return room.db.cah_game


def _is_builder(caller):
    """Return True if the caller has Builder permissions or above."""
    return caller.locks.check_lockstring(caller, "perm(Builder)")


# ---------------------------------------------------------------------------
# Main Command
# ---------------------------------------------------------------------------

class CmdCAH(Command):
    """
    Play Cards Against Re:Void.

    Usage:
      cah                     - Show current game status
      cah status              - Show current game status
      cah join                - Join the game lobby
      cah start [deck ...]    - Start the game (use named decks, or default to all)
      cah hand                - See your current hand (private)
      cah play <n> [n2]       - Play card number(s) from your hand
      cah pick <n>            - (Czar only) Pick the winning submission
      cah score               - Show the scoreboard
      cah leave               - Leave the game
      cah end                 - End the game (initiator or Builder only)
      cah decks               - List available card decks

    Example:
      cah start base nsfw revoid
      cah play 3
      cah play 1 5
      cah pick 2
    """

    key = "cah"
    aliases = ["cardsagainst"]
    locks = "cmd:all()"
    help_category = "Entertainment"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            caller.msg("|rYou need to be in a room to play.|n")
            return

        raw = (self.args or "").strip()
        parts = raw.split()
        subcmd = parts[0].lower() if parts else "status"
        subargs = parts[1:] if len(parts) > 1 else []

        dispatch = {
            "status": self._cmd_status,
            "join": self._cmd_join,
            "start": self._cmd_start,
            "hand": self._cmd_hand,
            "play": self._cmd_play,
            "pick": self._cmd_pick,
            "score": self._cmd_score,
            "leave": self._cmd_leave,
            "end": self._cmd_end,
            "decks": self._cmd_decks,
        }

        handler = dispatch.get(subcmd)
        if handler is None:
            caller.msg(
                f"|rUnknown sub-command '|w{subcmd}|r'. "
                f"Try |wcah|r or |wcah help|r.|n"
            )
            return

        handler(caller, room, subargs)

    # -----------------------------------------------------------------------
    # Sub-command: status
    # -----------------------------------------------------------------------

    def _cmd_status(self, caller, room, args):
        game = _get_or_create_game(room)

        if not game["active"] and game["phase"] == "lobby" and not game["players"]:
            caller.msg(
                "|xNo game of Cards Against Re:Void is running here.\n"
                "Type |wcah join|x to start a lobby, then |wcah start|x to begin.|n"
            )
            return

        lines = ["|x=== Cards Against Re:Void ===|n"]

        phase_display = {
            "lobby": "|xWaiting for players to join|n",
            "playing": "|wIn progress — players are submitting cards|n",
            "judging": "|yCzar is choosing the winner|n",
        }.get(game["phase"], game["phase"])

        lines.append(f"Phase: {phase_display}")
        lines.append(f"Round: {game['round']}")

        if game["players"]:
            czar_id = game["players"][game["czar_idx"]] if game["active"] else None
            lines.append("\nPlayers:")
            for pid in game["players"]:
                name = game["player_names"].get(pid, str(pid))
                score = game["scores"].get(pid, 0)
                tags = []
                if pid == czar_id:
                    tags.append("|yCzar|n")
                if pid == game.get("initiator_id"):
                    tags.append("|xhost|n")
                tag_str = " (" + ", ".join(tags) + ")" if tags else ""
                lines.append(f"  |w{name}|n{tag_str} — {score} pts")

        if game["active"] and game["black_card"]:
            lines.append(f"\nCurrent black card:\n{_format_black_card(game['black_card'])}")

        if game["phase"] == "playing" and game["active"]:
            czar_id = game["players"][game["czar_idx"]]
            waiting_on = [
                game["player_names"].get(pid, str(pid))
                for pid in game["players"]
                if pid != czar_id and pid not in game["played_cards"]
            ]
            if waiting_on:
                lines.append(
                    f"\n|xWaiting on: |w{'|n, |w'.join(waiting_on)}|n"
                )
            else:
                lines.append("\n|xAll submissions in — czar is judging.|n")

        caller.msg("\n".join(lines))

    # -----------------------------------------------------------------------
    # Sub-command: join
    # -----------------------------------------------------------------------

    def _cmd_join(self, caller, room, args):
        game = _get_or_create_game(room)
        pid = caller.id

        if game["active"]:
            caller.msg("|rA game is already in progress. Wait for the next round to join.|n")
            return

        if pid in game["players"]:
            caller.msg("|xYou're already in the lobby.|n")
            return

        game["players"].append(pid)
        game["player_names"][pid] = caller.name
        game["scores"][pid] = 0

        if game["initiator_id"] is None:
            game["initiator_id"] = pid

        room.msg_contents(
            f"|w{caller.name}|x has joined the Cards Against Re:Void lobby. "
            f"({len(game['players'])} player(s) waiting)|n"
        )

    # -----------------------------------------------------------------------
    # Sub-command: start
    # -----------------------------------------------------------------------

    def _cmd_start(self, caller, room, args):
        game = _get_or_create_game(room)
        pid = caller.id

        if game["active"]:
            caller.msg("|rA game is already running. Use |wcah end|r to stop it first.|n")
            return

        if pid != game.get("initiator_id") and not _is_builder(caller):
            caller.msg("|rOnly the host or a Builder can start the game.|n")
            return

        if len(game["players"]) < 2:
            caller.msg("|rAt least 2 players must join before the game can start.|n")
            return

        # Determine which decks to load
        deck_names = [a.lower() for a in args] if args else DEFAULT_DECKS
        available = list_decks()
        bad = [d for d in deck_names if d not in available]
        if bad:
            caller.msg(
                f"|rUnknown deck(s): |w{'|r, |w'.join(bad)}|r.\n"
                f"Available decks: |w{'|r, |w'.join(available.keys())}|n"
            )
            return

        try:
            black_cards, white_cards = load_decks(deck_names)
        except Exception as exc:
            caller.msg(f"|rFailed to load decks: {exc}|n")
            return

        if not black_cards:
            caller.msg("|rNo black cards loaded. Check your deck files.|n")
            return
        if len(white_cards) < len(game["players"]) * HAND_SIZE:
            caller.msg(
                f"|rNot enough white cards ({len(white_cards)}) to deal "
                f"{len(game['players'])} hands of {HAND_SIZE}. Add more decks.|n"
            )
            return

        game["black_deck"] = black_cards
        game["white_deck"] = white_cards
        game["discard_black"] = []
        game["discard_white"] = []
        game["decks_loaded"] = deck_names
        game["round"] = 1
        game["czar_idx"] = 0
        game["played_cards"] = {}
        game["hands"] = {}
        game["active"] = True

        # Deal hands
        for p in game["players"]:
            game["hands"][p] = []
            _deal_hand(game, p)

        # Draw first black card
        first_black = _draw_black(game)
        game["black_card"] = first_black
        game["phase"] = "playing"

        czar_id = game["players"][game["czar_idx"]]
        czar_name = game["player_names"].get(czar_id, "???")
        deck_str = ", ".join(deck_names)

        room.msg_contents(
            f"\n|m=== Cards Against Re:Void has started! ===|n\n"
            f"|xDecks: |w{deck_str}|n\n"
            f"|xPlayers: |w{'|n, |w'.join(game['player_names'].get(p, str(p)) for p in game['players'])}|n\n"
            f"\n|x--- Round 1 ---\n"
            f"Card Czar: |y{czar_name}|n\n\n"
            f"{_format_black_card(first_black)}\n\n"
            f"|x{czar_name} waits. Everyone else: use |wcah play <number>|x to submit.|n\n"
            f"|xType |wcah hand|x to see your cards (private).|n\n"
        )

    # -----------------------------------------------------------------------
    # Sub-command: hand
    # -----------------------------------------------------------------------

    def _cmd_hand(self, caller, room, args):
        game = _get_or_create_game(room)
        pid = caller.id

        if not game["active"]:
            caller.msg("|xNo game is running.|n")
            return

        if pid not in game["players"]:
            caller.msg("|xYou're not in this game.|n")
            return

        hand = game["hands"].get(pid, [])
        czar_id = game["players"][game["czar_idx"]]

        if pid == czar_id:
            caller.msg("|xYou are the Card Czar this round. You don't play cards — you judge them.|n")
            return

        if not hand:
            caller.msg("|xYour hand is empty.|n")
            return

        already_played = game["played_cards"].get(pid, [])

        lines = ["|x--- Your Hand (private) ---|n"]
        for i, card in enumerate(hand):
            marker = " |x(played)|n" if card in already_played else ""
            lines.append(f"  |w[{i + 1}]|n {card}{marker}")
        lines.append("|x--- End of hand ---|n")

        caller.msg("\n".join(lines))

    # -----------------------------------------------------------------------
    # Sub-command: play
    # -----------------------------------------------------------------------

    def _cmd_play(self, caller, room, args):
        game = _get_or_create_game(room)
        pid = caller.id

        if not game["active"]:
            caller.msg("|xNo game is running.|n")
            return

        if game["phase"] != "playing":
            caller.msg("|xCards can only be played during the playing phase.|n")
            return

        if pid not in game["players"]:
            caller.msg("|xYou're not in this game.|n")
            return

        czar_id = game["players"][game["czar_idx"]]
        if pid == czar_id:
            caller.msg("|xYou're the Card Czar this round. You judge, not play.|n")
            return

        if pid in game["played_cards"]:
            caller.msg("|xYou've already submitted cards this round.|n")
            return

        pick_count = game["black_card"]["pick"] if game["black_card"] else 1
        hand = game["hands"].get(pid, [])

        if not args:
            caller.msg(
                f"|rThis card requires you to play {pick_count} card(s).\n"
                f"Usage: |wcah play <number>|r (or |wcah play <n1> <n2>|r for pick 2)|n"
            )
            return

        # Parse indices
        try:
            indices = [int(a) for a in args]
        except ValueError:
            caller.msg("|rPlease provide card number(s), e.g.: |wcah play 3|r or |wcah play 1 4|n")
            return

        if len(indices) != pick_count:
            caller.msg(
                f"|rThis black card requires exactly {pick_count} card(s). "
                f"You provided {len(indices)}.|n"
            )
            return

        if len(set(indices)) != len(indices):
            caller.msg("|rYou can't play the same card twice in one submission.|n")
            return

        for idx in indices:
            if idx < 1 or idx > len(hand):
                caller.msg(
                    f"|rCard number {idx} is out of range. "
                    f"You have {len(hand)} cards (|wcah hand|r to see them).|n"
                )
                return

        # Pull the cards (1-indexed → 0-indexed), remove from hand
        selected = [hand[i - 1] for i in indices]
        for card in selected:
            hand.remove(card)

        game["played_cards"][pid] = selected

        caller.msg(
            f"|xYou played: |w{'|n / |w'.join(selected)}|n\n"
            f"|xWaiting for the other players and the Czar's judgment.|n"
        )
        room.msg_contents(
            f"|x{caller.name} has submitted their card(s).|n",
            exclude=caller,
        )

        # Check if all non-czar players have submitted
        non_czars = [p for p in game["players"] if p != czar_id]
        all_submitted = all(p in game["played_cards"] for p in non_czars)

        if all_submitted:
            game["phase"] = "judging"
            _show_submissions(room, game)

    # -----------------------------------------------------------------------
    # Sub-command: pick
    # -----------------------------------------------------------------------

    def _cmd_pick(self, caller, room, args):
        game = _get_or_create_game(room)
        pid = caller.id

        if not game["active"]:
            caller.msg("|xNo game is running.|n")
            return

        if game["phase"] != "judging":
            caller.msg("|xThe czar can only pick a winner during the judging phase.|n")
            return

        czar_id = game["players"][game["czar_idx"]]
        if pid != czar_id:
            caller.msg("|xOnly the Card Czar can pick a winner right now.|n")
            return

        if not args:
            caller.msg("|rUsage: |wcah pick <submission number>|n")
            return

        try:
            pick_num = int(args[0])
        except ValueError:
            caller.msg("|rPlease provide a number, e.g.: |wcah pick 2|n")
            return

        # Build ordered list of non-czar players who submitted
        submitters = [
            p for p in game["players"]
            if p != czar_id and p in game["played_cards"]
        ]

        if pick_num < 1 or pick_num > len(game["players"]):
            caller.msg(
                f"|rSubmission {pick_num} doesn't exist. "
                f"Submissions are numbered from the player list (1–{len(game['players'])}).|n"
            )
            return

        # pick_num corresponds to the player's position in game["players"] (1-indexed)
        target_pid = None
        non_czar_idx = 0
        for p in game["players"]:
            if p == czar_id:
                continue
            non_czar_idx += 1
            if non_czar_idx == pick_num - (1 if game["players"].index(czar_id) < game["players"].index(p) else 0):
                # Simpler: use the displayed numbering which is player index + 1 in players list
                pass

        # Resolve: the displayed number in _show_submissions is (player_list_idx + 1)
        # for non-czar players. Reconstruct that mapping.
        submission_map = {}
        for idx, p in enumerate(game["players"]):
            if p != czar_id and p in game["played_cards"]:
                submission_map[idx + 1] = p

        if pick_num not in submission_map:
            caller.msg(
                f"|rNo submission at position {pick_num}. "
                f"Valid numbers: |w{'|r, |w'.join(str(k) for k in sorted(submission_map))}|n"
            )
            return

        winner_id = submission_map[pick_num]
        winner_name = game["player_names"].get(winner_id, "???")
        winning_cards = game["played_cards"][winner_id]

        game["scores"][winner_id] = game["scores"].get(winner_id, 0) + 1
        new_score = game["scores"][winner_id]

        room.msg_contents(
            f"\n|m{caller.name} (Czar) picks submission {pick_num}!\n"
            f"Winner: |w{winner_name}|m!\n"
            f"Played: |w{'|m / |w'.join(winning_cards)}|m\n"
            f"{winner_name} now has {new_score} point(s).|n\n"
        )

        _next_round(room, game)

    # -----------------------------------------------------------------------
    # Sub-command: score
    # -----------------------------------------------------------------------

    def _cmd_score(self, caller, room, args):
        game = _get_or_create_game(room)

        if not game["players"]:
            caller.msg("|xNo game in progress.|n")
            return

        lines = ["|x=== Scoreboard ===|n"]
        ranked = sorted(
            game["players"],
            key=lambda p: game["scores"].get(p, 0),
            reverse=True,
        )
        for rank, pid in enumerate(ranked, 1):
            name = game["player_names"].get(pid, str(pid))
            score = game["scores"].get(pid, 0)
            lines.append(f"  {rank}. |w{name}|n — {score} pt(s)")

        caller.msg("\n".join(lines))

    # -----------------------------------------------------------------------
    # Sub-command: leave
    # -----------------------------------------------------------------------

    def _cmd_leave(self, caller, room, args):
        game = _get_or_create_game(room)
        pid = caller.id

        if pid not in game["players"]:
            caller.msg("|xYou're not in this game.|n")
            return

        game["players"].remove(pid)
        game["player_names"].pop(pid, None)
        game["scores"].pop(pid, None)
        game["hands"].pop(pid, None)
        game["played_cards"].pop(pid, None)

        room.msg_contents(
            f"|x{caller.name} has left the game.|n"
        )

        remaining = len(game["players"])

        if remaining == 0:
            room.db.cah_game = _new_game_state()
            room.msg_contents("|xThe game has ended — no players remain.|n")
            return

        if game["active"] and remaining < 2:
            room.db.cah_game = _new_game_state()
            room.msg_contents(
                "|xNot enough players to continue. The game has ended.|n"
            )
            return

        # If the czar left mid-game, advance czar index
        if game["active"]:
            # Keep czar_idx in bounds
            game["czar_idx"] = game["czar_idx"] % len(game["players"])

            # If we're in playing phase and they already submitted, check if done
            if game["phase"] == "playing":
                czar_id = game["players"][game["czar_idx"]]
                non_czars = [p for p in game["players"] if p != czar_id]
                if non_czars and all(p in game["played_cards"] for p in non_czars):
                    game["phase"] = "judging"
                    _show_submissions(room, game)

        # Reassign host if needed
        if pid == game.get("initiator_id") and game["players"]:
            game["initiator_id"] = game["players"][0]
            new_host = game["player_names"].get(game["initiator_id"], "???")
            room.msg_contents(f"|x{new_host} is now the host.|n")

    # -----------------------------------------------------------------------
    # Sub-command: end
    # -----------------------------------------------------------------------

    def _cmd_end(self, caller, room, args):
        game = _get_or_create_game(room)
        pid = caller.id

        if not game["players"] and not game["active"]:
            caller.msg("|xThere is no game to end.|n")
            return

        if pid != game.get("initiator_id") and not _is_builder(caller):
            caller.msg("|rOnly the host or a Builder can end the game.|n")
            return

        # Print final scores
        if game["players"]:
            lines = ["|m=== Game Over — Final Scores ===|n"]
            ranked = sorted(
                game["players"],
                key=lambda p: game["scores"].get(p, 0),
                reverse=True,
            )
            for rank, p in enumerate(ranked, 1):
                name = game["player_names"].get(p, str(p))
                score = game["scores"].get(p, 0)
                lines.append(f"  {rank}. |w{name}|n — {score} pt(s)")
            if ranked:
                top = game["player_names"].get(ranked[0], "???")
                lines.append(f"\n|mCongratulations to |w{top}|m!|n")
            room.msg_contents("\n".join(lines))

        room.db.cah_game = _new_game_state()
        room.msg_contents("|xCards Against Re:Void has ended. Thanks for playing.|n")

    # -----------------------------------------------------------------------
    # Sub-command: decks
    # -----------------------------------------------------------------------

    def _cmd_decks(self, caller, room, args):
        decks = list_decks()
        lines = ["|x=== Available Card Decks ===|n"]
        for name, desc in decks.items():
            lines.append(f"  |w{name}|n — {desc}")
        lines.append(
            "\n|xUse |wcah start <deck1> <deck2> ...|x to choose decks when starting.|n"
        )
        caller.msg("\n".join(lines))


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_CAH_CMDS = [CmdCAH]
