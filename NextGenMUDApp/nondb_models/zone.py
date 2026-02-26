from .quests import Quest, QuestStage, QuestCondition, QuestSchemaRegistry


class Zone:
    def __init__(self, id):
        self.id = id
        self.name = ""
        self.rooms = {}
        self.actors = {}
        self.description = ""
        self.common_knowledge = {}  # id -> knowledge content for LLM NPCs
        self.quests = {}  # Store Quest objects here

    def load_quests(self, data: dict) -> None:
        """Load quests from YAML data (the 'quests' section for this zone)."""
        zone_id = self.id
        
        # Get the registry singleton
        registry = QuestSchemaRegistry.get_instance()

        for q_id, q_data in data.items():
            
            # --- NEW: LOAD NESTED VARIABLES ---
            # If the user defines variables inside the quest, load them now.
            # We treat the 'q_id' as the category name.
            if 'variables' in q_data:
                # Construct the dict structure expected by the registry:
                # { category_name: { var_name: { ... } } }
                schema_payload = {q_id: q_data['variables']}
                registry.load_from_dict(schema_payload, zone_id=zone_id)
            # ----------------------------------

            stages = []
            for s_data in q_data.get('stages', []):
                conditions = []

                # Parse conditions
                cond_dict = s_data.get('conditions', {})
                for var, val_payload in cond_dict.items():
                    if isinstance(val_payload, dict) and 'op' in val_payload:
                        op = val_payload['op']
                        val = val_payload['val']
                    else:
                        op = 'eq'
                        val = val_payload
                    
                    conditions.append(QuestCondition(var, op, val))

                stages.append(QuestStage(
                    name=s_data.get('name', 'stage'),
                    description=s_data.get('description', ''),
                    sequence=s_data.get('sequence', 0),
                    conditions=conditions
                ))

            full_quest_id = f"{zone_id}.{q_id}"
            self.quests[q_id] = Quest(full_quest_id, q_data.get('title', q_id), stages, zone_id)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'rooms': {room_id: room.to_dict() for room_id, room in self.rooms.items()},
            'actors': self.actors,  # Make sure this is also serializable
            'description': self.description,
            'common_knowledge': self.common_knowledge,
        }

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def __str__(self):
        return self.__repr__()
