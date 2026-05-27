# -*- coding: utf-8 -*-
"""
Connection screen

This is the text to show the user when they first connect to the game (before
they log in).

To change the login screen in this module, do one of the following:

- Define a function `connection_screen()`, taking no arguments. This will be
  called first and must return the full string to act as the connection screen.
  This can be used to produce more dynamic screens.
- Alternatively, define a string variable in the outermost scope of this module
  with the connection string that should be displayed. If more than one such
  variable is given, Evennia will pick one of them at random.

The commands available to the user when the connection screen is shown
are defined in evennia.default_cmds.UnloggedinCmdSet. The parsing and display
of the screen is done by the unlogged-in "look" command.

"""

from django.conf import settings

from evennia import utils

CONNECTION_SCREEN = """
|m  ================================================================|n

  |M ██████╗ ███████╗  ║  ██╗   ██╗ ██████╗ ██╗██████╗|n
  |M ██╔══██╗██╔════╝  ║  ██║   ██║██╔═══██╗██║██╔══██╗|n
  |M ██████╔╝█████╗    ║  ╚██╗ ██╔╝██║   ██║██║██║  ██║|n
  |M ██╔══██╗██╔══╝    ║   ╚████╔╝ ██║   ██║██║██║  ██║|n
  |M ██║  ██║███████╗  ║    ╚██╔╝  ╚██████╔╝██║██████╔╝|n
  |M ╚═╝  ╚═╝╚══════╝  ║     ╚═╝    ╚═════╝ ╚═╝╚═════╝|n

  |m · · · · · R e s h a p i n g   t h e   V o i d · · · · ·|n

|m  ================================================================|n

   |wconnect <username> <password>|n  —  return to the Void
   |wcreate  <username> <password>|n  —  step into existence

   |xType |whelp|x for commands.  |wlook|x re-shows this screen.|n

   |xYour character persists in the world after you disconnect.
   Use |wquit|x to fully log out.|n

|m  ================================================================|n"""
