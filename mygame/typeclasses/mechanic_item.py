"""
typeclasses/mechanic_item.py

Base typeclass for mechanic items — consumable objects that install
a persistent game mechanic into a room zone when used on it.

In-game usage:
    use <item> on <zone>    — installs the mechanic; item is consumed

Subclasses must override:
    mechanic_key (str)
    install_into_zone(room, zone_name, installer) -> (bool, str)
"""

from evennia import DefaultObject


class MechanicItem(DefaultObject):
    """
    Base class for installable mechanic items.

    Subclasses define what mechanic they install by overriding
    `mechanic_key` and `install_into_zone()`.

    The CmdUse command handles finding the item, routing to
    install_into_zone(), and deleting the item on success.
    """

    mechanic_key = "base"

    def at_object_creation(self):
        super().at_object_creation()
        self.db.mechanic_key = self.mechanic_key

    def install_into_zone(self, room, zone_name, installer):
        """
        Write this mechanic's data into room.db.zones[zone_name]["mechanics"].

        Args:
            room        : the room object
            zone_name   : str, target zone key
            installer   : the character performing the install

        Returns:
            (bool, str) — (success, message to show the installer)

        Subclasses must override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement install_into_zone()"
        )
