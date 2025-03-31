from .models import Player, GameSave, GameItem, PlayerInventory
from django.contrib.auth.models import User

def create_player(username, name=None):
    """
    Create a new player
    """
    if name is None:
        name = username
        
    # Try to get existing user or create a new one
    user, created = User.objects.get_or_create(username=username)
    
    # Create player linked to user
    player, created = Player.objects.get_or_create(
        user=user,
        defaults={'name': name}
    )
    
    return player

def save_game(player_name, save_name, game_state):
    """
    Save the game state to the database
    
    Args:
        player_name (str): Name of the player
        save_name (str): Name for this save
        game_state (dict): Game state dictionary
    
    Returns:
        GameSave: The created or updated game save
    """
    # Get or create player
    player, created = Player.objects.get_or_create(name=player_name)
    
    # Try to find existing save or create new one
    game_save, created = GameSave.objects.get_or_create(
        player=player,
        save_name=save_name,
        defaults={'game_state_json': '{}'}
    )
    
    # Update game state
    game_save.set_game_state(game_state)
    game_save.save()
    
    return game_save

def load_game(player_name, save_name):
    """
    Load game state from database
    
    Args:
        player_name (str): Name of the player
        save_name (str): Name of the save to load
    
    Returns:
        dict: Game state dictionary or None if not found
    """
    try:
        player = Player.objects.get(name=player_name)
        game_save = GameSave.objects.get(player=player, save_name=save_name)
        return game_save.get_game_state()
    except (Player.DoesNotExist, GameSave.DoesNotExist):
        return None

def list_saves(player_name):
    """
    List all saves for a player
    
    Args:
        player_name (str): Name of the player
    
    Returns:
        list: List of save names
    """
    try:
        player = Player.objects.get(name=player_name)
        saves = GameSave.objects.filter(player=player)
        return [(save.save_name, save.updated_at) for save in saves]
    except Player.DoesNotExist:
        return []

def delete_save(player_name, save_name):
    """
    Delete a save
    
    Args:
        player_name (str): Name of the player
        save_name (str): Name of the save to delete
    
    Returns:
        bool: True if deleted, False if not found
    """
    try:
        player = Player.objects.get(name=player_name)
        game_save = GameSave.objects.get(player=player, save_name=save_name)
        game_save.delete()
        return True
    except (Player.DoesNotExist, GameSave.DoesNotExist):
        return False
