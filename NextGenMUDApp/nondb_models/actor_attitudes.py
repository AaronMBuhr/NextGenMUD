from enum import Enum, auto

class ActorAttitude(Enum):
    """
    Defines the attitude one actor has towards another.
    Used for determining behavior, combat eligibility, and social interactions.
    """
    HOSTILE = auto()      # Will attack on sight
    UNFRIENDLY = auto()   # Won't attack unprovoked but won't help
    NEUTRAL = auto()      # Default state
    FRIENDLY = auto()     # Will help, won't attack 
    CHARMED = auto()      # Temporarily friendly, magic-induced
    DOMINATED = auto()    # Fully controlled by source actor

    def can_attack(self) -> bool:
        """Return whether this attitude allows initiating attacks"""
        return self in [ActorAttitude.HOSTILE, ActorAttitude.UNFRIENDLY]
    
    def will_help(self) -> bool:
        """Return whether this attitude involves willingness to help"""
        return self in [ActorAttitude.FRIENDLY, ActorAttitude.CHARMED, ActorAttitude.DOMINATED]
    
    def is_magically_influenced(self) -> bool:
        """Return whether this attitude is due to magical influence"""
        return self in [ActorAttitude.CHARMED, ActorAttitude.DOMINATED]
    
    def broken_by_attack(self) -> bool:
        """Return whether this attitude breaks if the source attacks"""
        return self == ActorAttitude.CHARMED  # Dominated is not broken by attack

    def __str__(self):
        attitude_names = {
            ActorAttitude.HOSTILE: "hostile",
            ActorAttitude.UNFRIENDLY: "unfriendly", 
            ActorAttitude.NEUTRAL: "neutral",
            ActorAttitude.FRIENDLY: "friendly",
            ActorAttitude.CHARMED: "charmed",
            ActorAttitude.DOMINATED: "dominated"
        }
        return attitude_names.get(self, "unknown")
