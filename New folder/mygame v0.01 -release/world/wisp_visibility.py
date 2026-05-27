# world/wisp_visibility.py
"""
Manages wisp visibility rules.
Determines whether a given wisp is visible 
to a given observer in a given room.
"""

import random
from world.pool_loader import load_pool


class WispVisibility:
    
    @staticmethod
    def wisp_visible_to(wisp_account, observer, room):
        """
        Determine if this wisp is visible to this observer in this room.
        
        Args:
            wisp_account: The Account object of the wisp
            observer: The Character object of the observer
            room: The Room object they're both in
            
        Returns:
            bool: True if wisp is visible to observer
        """
        # Hub rooms — always visible to everyone
        if (hasattr(room.db, 'wisp_always_visible') and 
                room.db.wisp_always_visible):
            return True
        
        # Tutorial/Forming rooms — always visible
        if hasattr(room.db, 'is_forming') and room.db.is_forming:
            return True
        
        # Wisp has explicitly revealed to this observer's account
        revealed_to = wisp_account.db.wisp_revealed_to or set()
        if hasattr(observer, 'account') and observer.account:
            if observer.account.id in revealed_to:
                return True
        
        # Observer has opted into seeing all wisps
        observer_account = (
            observer.account 
            if hasattr(observer, 'account') 
            else None
        )
        if observer_account:
            pref = observer_account.db.wisp_preference or "hidden"
            if pref == "visible":
                return True
        
        # Default — invisible
        return False
    
    @staticmethod
    def get_room_wisps(room, observer=None):
        """
        Get all wisps currently in a room.
        If observer is provided, returns only wisps visible to them.
        If observer is None, returns all wisps in the room.
        
        Args:
            room: Room object
            observer: Character object (optional)
            
        Returns:
            list: Account objects of wisps in the room
        """
        from evennia import SESSION_HANDLER
        wisps = []
        
        for session in SESSION_HANDLER.get_sessions():
            account = session.get_account()
            puppet = session.get_puppet()
            
            if not account:
                continue
            
            # Skip if playing a character
            if puppet:
                continue
            
            # Skip if not in this room
            wisp_location = account.db.wisp_location
            if wisp_location != room:
                continue
            
            # If observer provided, check visibility
            if observer is not None:
                if not WispVisibility.wisp_visible_to(
                    account, observer, room
                ):
                    continue
            
            wisps.append(account)
        
        return wisps
    
    @staticmethod
    def get_haunting_lines(room):
        """
        Get ambient lines contributed by haunting wisps in this room.
        Only from wisps with haunt enabled.
        Only in rooms where the wisp would be invisible.
        
        Args:
            room: Room object
            
        Returns:
            list: Ambient lines, colorized with wisp's mood color
        """
        from evennia import SESSION_HANDLER

        # Haunting only in non-hub rooms
        if (hasattr(room.db, 'wisp_always_visible') and
                room.db.wisp_always_visible):
            return []
        
        lines = []
        
        for session in SESSION_HANDLER.get_sessions():
            account = session.get_account()
            puppet = session.get_puppet()
            
            if not account or puppet:
                continue
            if account.db.wisp_location != room:
                continue
            if not account.db.wisp_haunt:
                continue
            
            # Get mood-specific and general pools
            mood = account.db.wisp_mood or "neutral"
            pools = load_pool("wisp", "haunting")
            
            mood_pool = pools.get(f"mood_{mood}", [])
            general_pool = pools.get("general", [])
            combined = mood_pool + general_pool
            
            # Add player's personal ambient pool
            personal_pool = account.db.wisp_ambient_pool or []
            combined.extend(personal_pool)
            
            if not combined:
                continue

            line = random.choice(combined)
            
            # Colorize with the wisp's mood color
            try:
                color = account.wisp_color_code
            except Exception:
                color = "|w"
            
            lines.append(f"{color}{line}|n")
        
        return lines