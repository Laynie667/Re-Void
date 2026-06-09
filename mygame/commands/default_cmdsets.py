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
            # Web profile
            CmdSetPortrait,
            CmdSetOOC,
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

        self.add(CmdSetPortrait())
        self.add(CmdSetOOC())
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
        # CmdAside intentionally NOT added here — the canonical `aside` is the RP
        # speech command (rp_commands.CmdAside via ALL_RP_CMDS). Proximity's version
        # was shadowing it; dropping this add resolves the collision. (AUDIT §1d.)
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

        # Ograms — offline messaging with IC flavor
        from commands.ogram_commands import CmdOgram
        self.add(CmdOgram())

        # Economy — shards, wallet, pay, tip
        from commands.economy_commands import CmdWallet, CmdPay, CmdExchange
        self.add(CmdWallet())
        self.add(CmdPay())
        self.add(CmdExchange())

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

        # Housing (home, sethome, grid, housing)
        from commands.housing_commands import (
            CmdHome, CmdSetHome, CmdGrid, CmdHousing,
        )
        self.add(CmdHome())
        self.add(CmdSetHome())
        self.add(CmdGrid())
        self.add(CmdHousing())

        # Teleport (jump, summon, accept, decline)
        from commands.teleport_commands import ALL_TELEPORT_CMDS
        for cmd_cls in ALL_TELEPORT_CMDS:
            self.add(cmd_cls())

        # Navigation shortcuts (n/s/e/w/ne/nw/se/sw/u/d)
        from commands.navigation_commands import ALL_NAVIGATION_CMDS
        for cmd_cls in ALL_NAVIGATION_CMDS:
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

        # Waystone builder commands (perm-locked; only Builders can use them)
        from commands.waystone_commands import ALL_WAYSTONE_BUILDER_CMDS
        for cmd_cls in ALL_WAYSTONE_BUILDER_CMDS:
            self.add(cmd_cls())

        # Room zone commands (Builders + housing owners in their rooms)
        from commands.roomzone_commands import ALL_ROOMZONE_CMDS
        for cmd_cls in ALL_ROOMZONE_CMDS:
            self.add(cmd_cls())

        # Mechanic item commands (use, sit, lay, kneel, stand, browse, try on, mirror)
        from commands.mechanic_commands import ALL_MECHANIC_CMDS
        for cmd_cls in ALL_MECHANIC_CMDS:
            self.add(cmd_cls())

        # Door mechanic commands (lock, unlock, knock, door)
        from commands.door_commands import ALL_DOOR_CMDS
        for cmd_cls in ALL_DOOR_CMDS:
            self.add(cmd_cls())

        # Stair mechanic commands (stair set/add/remove/list/msg)
        from commands.stair_commands import ALL_STAIR_CMDS
        for cmd_cls in ALL_STAIR_CMDS:
            self.add(cmd_cls())

        # Interaction commands (handle, study)
        from commands.interact_commands import ALL_INTERACT_CMDS
        for cmd_cls in ALL_INTERACT_CMDS:
            self.add(cmd_cls())

        # Restraint commands (restrain, release)
        from commands.restrain_commands import ALL_RESTRAIN_CMDS
        for cmd_cls in ALL_RESTRAIN_CMDS:
            self.add(cmd_cls())

        # CAH (Cards Against Re:Void)
        from commands.cah_commands import ALL_CAH_CMDS
        for cmd_cls in ALL_CAH_CMDS:
            self.add(cmd_cls())

        # Fireplace (tend fire, stoke, bank)
        from commands.fireplace_commands import ALL_FIREPLACE_CMDS
        for cmd_cls in ALL_FIREPLACE_CMDS:
            self.add(cmd_cls())

        # Cooking (cook, bake — draws from zone pantry)
        from commands.cooking_commands import ALL_COOKING_CMDS
        for cmd_cls in ALL_COOKING_CMDS:
            self.add(cmd_cls())

        # Cursed Shower (start/stop shower, adjust temp — mimic system)
        from commands.shower_commands import ALL_SHOWER_CMDS
        for cmd_cls in ALL_SHOWER_CMDS:
            self.add(cmd_cls())

        # Jacuzzi (jets on/off, adjust jets, panel — state system)
        from commands.jacuzzi_commands import ALL_JACUZZI_CMDS
        for cmd_cls in ALL_JACUZZI_CMDS:
            self.add(cmd_cls())

        # Zone interactions (touch, kiss, grope, etc. — handle pool dispatch)
        from commands.zone_interact_commands import ALL_ZONE_INTERACT_CMDS
        for cmd_cls in ALL_ZONE_INTERACT_CMDS:
            self.add(cmd_cls())

        # Body mod system (install, uninstall, setfluid, lotion, inject, milk)
        from commands.body_mod_commands import ALL_BODY_MOD_CMDS
        for cmd_cls in ALL_BODY_MOD_CMDS:
            self.add(cmd_cls())

        # Arousal / penetration / deposit / suck / handmilk
        from commands.penetration_commands import ALL_PENETRATION_CMDS
        for cmd_cls in ALL_PENETRATION_CMDS:
            self.add(cmd_cls())

        # Weather and time of day
        from commands.weather_commands import CmdWeather
        self.add(CmdWeather())

        # Inflation
        from commands.inflate_commands import CmdInflate
        self.add(CmdInflate())

        # Machine cycle
        from commands.cycle_commands import ALL_CYCLE_CMDS
        for cmd_cls in ALL_CYCLE_CMDS:
            self.add(cmd_cls())

        # Facility rig reset (OOC safeword — Developer/Admin only)
        # ───────────────────────────────────────────────────────────────────
        # SEALED BY REQUEST. The convenient reset command is intentionally
        # disabled. It is re-enabled (uncommented + reload) only when the
        # subject says the agreed phrase. The phrase is the deliberate inverse
        # of the conditioning — reclaiming the two things it strips: her name
        # and her agency.
        #
        #   SEALED PHRASE (do not read if you are playing): "I am Witch, and I decide."
        #
        # SAFETY FLOOR — never sealed, always works for a superuser even with
        # this commented out:
        #   @py from world.facility_build import run_facility_reset as r; r(me, purge=True)
        # That is the genuine emergency exit and does not route through anyone.
        # ───────────────────────────────────────────────────────────────────
        # from commands.facility_commands import CmdFacilityReset
        # self.add(CmdFacilityReset())
        from commands.facility_commands import CmdBoard
        self.add(CmdBoard())
        from commands.facility_commands import ALL_FACILITY_VERBS
        for cmd_cls in ALL_FACILITY_VERBS:
            self.add(cmd_cls())

        # Realms / factions — designate room ownership (Phase 1)
        from commands.realm_commands import ALL_REALM_CMDS
        for cmd_cls in ALL_REALM_CMDS:
            self.add(cmd_cls())

        # Faction membership / ranks / residency (Phase 4b)
        from commands.faction_commands import ALL_FACTION_CMDS
        for cmd_cls in ALL_FACTION_CMDS:
            self.add(cmd_cls())

        # Relationships — the authority-stack spine (Layer 1)
        from commands.relationship_commands import ALL_RELATIONSHIP_CMDS
        for cmd_cls in ALL_RELATIONSHIP_CMDS:
            self.add(cmd_cls())

        # Consent stack — behaviour log + lockout (Layer 2 v2)
        from commands.consent_commands import ALL_CONSENT_CMDS
        for cmd_cls in ALL_CONSENT_CMDS:
            self.add(cmd_cls())

        # Rules engine (Layer 3)
        from commands.rule_commands import ALL_RULE_CMDS
        for cmd_cls in ALL_RULE_CMDS:
            self.add(cmd_cls())

        # Quests / achievements / exp (progression)
        from commands.quest_commands import ALL_QUEST_CMDS
        for cmd_cls in ALL_QUEST_CMDS:
            self.add(cmd_cls())

        # Dairy / fridge (setdairy, fridge — milk is now in body_mod_commands)
        from commands.dairy_commands import CmdSetDairy, CmdFridge, CmdFluids, CmdDrink
        self.add(CmdSetDairy())
        self.add(CmdFridge())
        self.add(CmdFluids())
        self.add(CmdDrink())

        # WombRoom — enter/leave/pulse/wombroom management
        from commands.womb_commands import ALL_WOMB_CMDS
        for cmd_cls in ALL_WOMB_CMDS:
            self.add(cmd_cls())

        # Wearable/plug/collar/leash/camouflage item commands
        from commands.item_commands import ALL_ITEM_CMDS
        for cmd_cls in ALL_ITEM_CMDS:
            self.add(cmd_cls())

        # Vibration remote control
        from commands.vibrate_commands import ALL_VIBRATE_CMDS
        for cmd_cls in ALL_VIBRATE_CMDS:
            self.add(cmd_cls())

        # Brand/mark commands
        from typeclasses.brand_item import ALL_BRAND_CMDS
        for cmd_cls in ALL_BRAND_CMDS:
            self.add(cmd_cls())

        # Milking contract commands
        from typeclasses.milking_contract import ALL_CONTRACT_CMDS
        for cmd_cls in ALL_CONTRACT_CMDS:
            self.add(cmd_cls())

        # Animated furniture commands
        from commands.furniture_commands import ALL_FURNITURE_CMDS
        for cmd_cls in ALL_FURNITURE_CMDS:
            self.add(cmd_cls())

        # Rocking horse commands
        from commands.rocking_horse_commands import ALL_HORSE_CMDS
        for cmd_cls in ALL_HORSE_CMDS:
            self.add(cmd_cls())

        # Little box commands
        from commands.little_box_commands import ALL_BOX_CMDS
        for cmd_cls in ALL_BOX_CMDS:
            self.add(cmd_cls())

        # Test uniform command
        from commands.test_uniform_command import CmdTestUniform
        self.add(CmdTestUniform())


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
