"""
Command sets

All commands in the game must be grouped in a cmdset.  A given command
can be part of any number of cmdsets and cmdsets can be added/removed
and merged onto entities at runtime.

To create new commands to populate the cmdset, see
`commands/command.py`.

This module wraps the default command sets of Evennia; overloads them
to add/remove commands from the default lineup. You can create your
own cmdsets by inheriting from them or directly from `evennia.CmdSet`.

"""

from evennia import default_cmds


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    """
    The CharacterCmdSet contains all commands available
    to a character in the game world.
    """
    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()

        # Character commands
        from commands.character_commands import (
            # Identity
            CmdSetName,
            CmdSetPronouns,
            CmdSetSpecies,
            CmdSetAge,
            # Description
            CmdSetDesc,
            CmdSetOutfit,
            CmdSetBodyLang,
            CmdSetMood,
            CmdSetMoodTell,
            CmdSetPresence,
            CmdSetProxTell,
            CmdSetScent,
            CmdSetVoice,
            CmdSetSayVerb,
            CmdSetTouch,
            CmdSetBio,
            CmdSetIntimate,
            # Zones
            CmdZone,
            # Clothing
            CmdWear,
            CmdRemove,
            CmdInsert,
            CmdUndress,
            CmdDress,
            CmdStraighten,
            # Wardrobe
            CmdWardrobe,
            # Outfits
            CmdOutfit,
            # Markings
            CmdMarking,
            # Title
            CmdTitle,
            # RP hooks
            CmdRPHook,
            # Sheet
            CmdSheet,
            # Consent
            CmdConsent,
            CmdBlock,
        )

        self.add(CmdSetName())
        self.add(CmdSetPronouns())
        self.add(CmdSetSpecies())
        self.add(CmdSetAge())
        self.add(CmdSetDesc())
        self.add(CmdSetOutfit())
        self.add(CmdSetBodyLang())
        self.add(CmdSetMood())
        self.add(CmdSetMoodTell())
        self.add(CmdSetPresence())
        self.add(CmdSetProxTell())
        self.add(CmdSetScent())
        self.add(CmdSetVoice())
        self.add(CmdSetSayVerb())
        self.add(CmdSetTouch())
        self.add(CmdSetBio())
        self.add(CmdSetIntimate())
        self.add(CmdZone())
        self.add(CmdWear())
        self.add(CmdRemove())
        self.add(CmdInsert())
        self.add(CmdUndress())
        self.add(CmdDress())
        self.add(CmdStraighten())
        self.add(CmdWardrobe())
        self.add(CmdOutfit())
        self.add(CmdMarking())
        self.add(CmdTitle())
        self.add(CmdRPHook())
        self.add(CmdSheet())
        self.add(CmdConsent())
        self.add(CmdBlock())

        # Character setup
        from commands.chargen import CmdChargen
        self.add(CmdChargen())

        # Core RP communication
        # (CmdOOC here handles both in-scene OOC comments and return-to-wisp)
        from commands.rp_commands import ALL_RP_CMDS
        for cmd_cls in ALL_RP_CMDS:
            self.add(cmd_cls())

        # Proximity
        from commands.proximity_commands import (
            CmdApproach,
            CmdWithdraw,
            CmdBeside,
            CmdAside,
            CmdProx,
        )
        self.add(CmdApproach())
        self.add(CmdWithdraw())
        self.add(CmdBeside())
        self.add(CmdAside())
        self.add(CmdProx())

        # Social emotes (all 134 emotes + CmdPermit)
        from commands.social_commands import ALL_SOCIAL_CMDS
        for cmd_cls in ALL_SOCIAL_CMDS:
            self.add(cmd_cls())

        # Scene management + pose order
        from commands.scene_commands import ALL_SCENE_CMDS
        for cmd_cls in ALL_SCENE_CMDS:
            self.add(cmd_cls())

        # Player safety (safeword, yellow — always available)
        from commands.safety_commands import ALL_SAFETY_CMDS
        for cmd_cls in ALL_SAFETY_CMDS:
            self.add(cmd_cls())

        # Admin safety tools (perm-locked; non-admins can't use them)
        from commands.safety_commands import ALL_SAFETY_ADMIN_CMDS
        for cmd_cls in ALL_SAFETY_ADMIN_CMDS:
            self.add(cmd_cls())

        # RP tools (flock, restrain, lead, prop, detail, stage, mark)
        from commands.rp_tools_commands import ALL_RP_TOOLS_CMDS
        for cmd_cls in ALL_RP_TOOLS_CMDS:
            self.add(cmd_cls())

        # Comms (tell, reply, page, channel, ws, mail)
        from commands.comms_commands import ALL_COMMS_CMDS
        for cmd_cls in ALL_COMMS_CMDS:
            self.add(cmd_cls())

        # Prefs (dnd, afk, highlight, filter, notify, friends, moodcarry, wispname)
        from commands.prefs_commands import ALL_PREFS_CHAR_CMDS
        for cmd_cls in ALL_PREFS_CHAR_CMDS:
            self.add(cmd_cls())

        # Bio fields (bio add/set/remove/order/show)
        from commands.bio_commands import ALL_BIO_CMDS
        for cmd_cls in ALL_BIO_CMDS:
            self.add(cmd_cls())

        # Relationship / contacts (rel list/add/remove/note/desc)
        from commands.rel_commands import ALL_REL_CMDS
        for cmd_cls in ALL_REL_CMDS:
            self.add(cmd_cls())

        # Freeform (place, slock, plock, sensory layers)
        from commands.freeform_commands import ALL_FREEFORM_CMDS
        for cmd_cls in ALL_FREEFORM_CMDS:
            self.add(cmd_cls())

        # Builder commands (perm-locked; only Builders can use them)
        from commands.builder_commands import ALL_BUILDER_CMDS
        for cmd_cls in ALL_BUILDER_CMDS:
            self.add(cmd_cls())

        # NPC builder commands (perm-locked; only Builders can use them)
        from commands.npc_commands import ALL_NPC_BUILDER_CMDS
        for cmd_cls in ALL_NPC_BUILDER_CMDS:
            self.add(cmd_cls())

        # NPC player commands (extra, greet, ask, nservice)
        from commands.npc_commands import ALL_NPC_PLAYER_CMDS
        for cmd_cls in ALL_NPC_PLAYER_CMDS:
            self.add(cmd_cls())



class AccountCmdSet(default_cmds.AccountCmdSet):
    """
    This is the cmdset available to the Account at all times.
    These commands are available whether the account is OOC
    as a wisp or IC as a character.
    """
    key = "DefaultAccount"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()

        # Wisp identity commands
        from commands.wisp_commands import (
            CmdMood,
            CmdWDesc,
            CmdWColor,
            CmdWSize,
            CmdWSignature,
            CmdWAmbient,
            CmdWPreview,
            CmdHaunt,
            CmdReveal,
            CmdWispPref,
            CmdWispScore,
            CmdWispWho,
            CmdIC,
            CmdCharacters,
            CmdOOC,
            # Wisp navigation — look and movement
            CmdWispLook,
            CmdWispMove,
            # Wisp communication — context-aware base commands
            CmdWispSay,
            CmdWispPose,
            CmdWispEmote,
            CmdWispWhisper,
            CmdWispMutter,
            CmdWispShout,
            CmdWVoice,
            CmdWLog,
        )

        self.add(CmdMood())
        self.add(CmdWDesc())
        self.add(CmdWColor())
        self.add(CmdWSize())
        self.add(CmdWSignature())
        self.add(CmdWAmbient())
        self.add(CmdWPreview())
        self.add(CmdHaunt())
        self.add(CmdReveal())
        self.add(CmdWispPref())
        self.add(CmdWispScore())
        self.add(CmdWispWho())
        self.add(CmdIC())
        self.add(CmdCharacters())
        self.add(CmdOOC())

        # Wisp navigation — look and move through exits
        self.add(CmdWispLook())
        self.add(CmdWispMove())

        # Wisp communication — same keys as IC commands, AccountCmdSet only
        self.add(CmdWispSay())
        self.add(CmdWispPose())
        self.add(CmdWispEmote())
        self.add(CmdWispWhisper())
        self.add(CmdWispMutter())
        self.add(CmdWispShout())
        self.add(CmdWVoice())
        self.add(CmdWLog())

        # Comms — OOC access to channels + wisp ping
        from commands.comms_commands import ALL_COMMS_ACCT_CMDS
        for cmd_cls in ALL_COMMS_ACCT_CMDS:
            self.add(cmd_cls())

        # Prefs — OOC subset (no afk/moodcarry — those are character-only)
        from commands.prefs_commands import ALL_PREFS_ACCT_CMDS
        for cmd_cls in ALL_PREFS_ACCT_CMDS:
            self.add(cmd_cls())


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    """
    Command set available to the Session before being logged in.  This
    holds commands like creating a new account, logging in, etc.
    """

    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #


class SessionCmdSet(default_cmds.SessionCmdSet):
    """
    This cmdset is made available on Session level once logged in. It
    is empty by default.
    """

    key = "DefaultSession"

    def at_cmdset_creation(self):
        """
        This is the only method defined in a cmdset, called during
        its creation. It should populate the set with command instances.

        As and example we just add the empty base `Command` object.
        It prints some info.
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
