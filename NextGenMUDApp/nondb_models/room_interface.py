from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .actor_interface import ActorInterface
from ..basic_types import DescriptiveFlags


class RoomFlags(DescriptiveFlags):
    DARK = 2**0
    NO_MOB = 2**1
    INDOORS = 2**2
    NO_MAGIC = 2**3
    NO_SUMMON = 2**4
    FLIGHT_NEEDED = 2**5
    UNDERWATER = 2**6


@dataclass
class Exit:
    """
    Represents an exit from a room.
    
    Exits can optionally have doors which can be opened, closed, locked, and unlocked.
    Doors can be linked to exits in other rooms so that locking/unlocking one affects both.
    
    YAML format:
        exits:
          north:
            destination: other_room
          south:
            destination: zone.room
            description: You see a dark tunnel leading into shadow.
            door:
              name: oak door
              keywords: [door, oak]
              is_closed: true
              is_locked: true
              key_id: brass_key
              linked_exit: zone.room.north  # When this door is unlocked, so is that one
          up:
            destination: tower_top
            description: A spiral staircase winds upward.
    """
    destination: str
    description: Optional[str] = None  # Shown when player does "look <direction>"
    door_name: Optional[str] = None
    door_keywords: List[str] = field(default_factory=list)
    is_closed: bool = False
    is_locked: bool = False
    key_id: Optional[str] = None
    linked_exit: Optional[str] = None  # Format: zone.room.direction
    triggers: Dict[str, List[Any]] = field(default_factory=dict)  # on_open, on_close, on_lock, on_unlock
    
    @property
    def has_door(self) -> bool:
        return self.door_name is not None
    
    @property
    def art_name(self) -> str:
        return f"the {self.door_name}" if self.door_name else "the exit"
    
    @property
    def art_name_cap(self) -> str:
        return f"The {self.door_name}" if self.door_name else "The exit"
    
    def matches_keyword(self, keyword: str) -> bool:
        """Check if this exit's door matches a keyword."""
        keyword_lower = keyword.lower()
        if self.door_name and keyword_lower in self.door_name.lower():
            return True
        return any(keyword_lower == kw.lower() for kw in self.door_keywords)
    
    @classmethod
    def from_yaml(cls, exit_data: dict) -> 'Exit':
        """Create an Exit from YAML data."""
        if isinstance(exit_data, str):
            # Simple format: just a destination string
            return cls(destination=exit_data)
        
        destination = exit_data.get('destination', '')
        description = exit_data.get('description')
        
        # Check for door properties
        door_data = exit_data.get('door', {})
        if door_data:
            return cls(
                destination=destination,
                description=description,
                door_name=door_data.get('name'),
                door_keywords=door_data.get('keywords', []),
                is_closed=door_data.get('is_closed', False),
                is_locked=door_data.get('is_locked', False),
                key_id=door_data.get('key_id'),
                linked_exit=door_data.get('linked_exit'),
                triggers=door_data.get('triggers', {})
            )
        
        return cls(destination=destination, description=description)
    
    def to_dict(self) -> dict:
        """Serialize to dict for saving."""
        result = {'destination': self.destination}
        if self.has_door:
            result['door'] = {
                'name': self.door_name,
                'keywords': self.door_keywords,
                'is_closed': self.is_closed,
                'is_locked': self.is_locked,
            }
            if self.key_id:
                result['door']['key_id'] = self.key_id
            if self.linked_exit:
                result['door']['linked_exit'] = self.linked_exit
        return result


class RoomInterface:

    @abstractmethod
    def remove_character(self, character: 'Character'):
        raise NotImplementedError
        
    @abstractmethod
    def add_character(self, character: 'Character'):
        raise NotImplementedError

    @abstractmethod
    def remove_object(self, obj: 'Object'):
        raise NotImplementedError

    @abstractmethod
    def add_object(self, obj: 'Object'):
        raise NotImplementedError
    
    @abstractmethod
    def get_characters(self) -> List['Character']:
        raise NotImplementedError
    
