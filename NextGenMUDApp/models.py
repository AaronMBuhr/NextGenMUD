from django.db import models
from django.contrib.auth.models import User
import json

class Player(models.Model):
    """Represents a player in the game"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class GameSave(models.Model):
    """Stores game save data"""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='game_saves')
    save_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Store game state as JSON
    game_state_json = models.TextField()
    
    def set_game_state(self, game_state_dict):
        """Set the game state from a dictionary"""
        self.game_state_json = json.dumps(game_state_dict)
    
    def get_game_state(self):
        """Get the game state as a dictionary"""
        return json.loads(self.game_state_json)
    
    def __str__(self):
        return f"{self.player.name}'s save: {self.save_name}"

class GameItem(models.Model):
    """Represents items in the game"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    item_type = models.CharField(max_length=50)
    properties_json = models.TextField(default="{}")
    
    def set_properties(self, properties_dict):
        """Set item properties from a dictionary"""
        self.properties_json = json.dumps(properties_dict)
    
    def get_properties(self):
        """Get item properties as a dictionary"""
        return json.loads(self.properties_json)
    
    def __str__(self):
        return self.name

class PlayerInventory(models.Model):
    """Represents a player's inventory"""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='inventory')
    game_save = models.ForeignKey(GameSave, on_delete=models.CASCADE, related_name='inventories')
    item = models.ForeignKey(GameItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    
    def __str__(self):
        return f"{self.player.name}'s {self.item.name} x{self.quantity}"
