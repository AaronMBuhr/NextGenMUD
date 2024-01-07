from enum import Enum

class ActorType(Enum):
    CHARACTER = 1
    OBJECT = 2
    ROOM = 3


class Actor:

    def __init__(self, actor_type: ActorType, id: str):
        self.actor_type_ = actor_type
        self.id_ = id

    def __str__(self):
        return self.id_

    def __repr__(self):
        return self.id_

    @property
    def actor_type(self):
        return self.actor_type_
    
    @actor_type.setter
    def actor_type(self, value):
        self.actor_type_ = value

    @property
    def name(self):
        return self.id_

    @name.setter
    def name(self, value):
        self.id_ = value


class ExitDirectionsEnum(Enum):
    NORTH = 1
    SOUTH = 2
    EAST = 3
    WEST = 4
    UP = 5
    DOWN = 6
    NORTHEAST = 7
    NORTHWEST = 8
    SOUTHEAST = 9
    SOUTHWEST = 10
    IN = 11
    OUT = 12

class ExitDirections:
    def __init__(self, direction_list):
        self.direction_list = direction_list

    def __getattr__(self, name):
        if name in ExitDirectionsEnum.__members__:
            enum_member = ExitDirectionsEnum[name]
            return self.direction_list[enum_member.value - 1]
        raise AttributeError(f"'ExitDirections' object has no attribute '{name}'")


class Room(Actor):
    
        def __init__(self, name):
            super().__init__(ActorType.ROOM, name)
            self.exits_ = []
            self.description_ = ""
    
        @property
        def exits(self):
            return self.exits_
    
        @exits.setter
        def exits(self, value):
            self.exits_ = value
        
        @property
        def description(self):
            return self.description_
        
        @description.setter
        def description(self, value):
            self.description_ = value


class Character(Actor):
    
    def __init__(self, name):
        super().__init__(ActorType.CHARACTER, name)
        self.location_ = None
    
    @property
    def location(self):
        return self.location_
    
    @location.setter
    def location(self, value):
        self.location_ = value
