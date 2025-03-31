from django.contrib import admin
from .models import Player, GameSave, GameItem, PlayerInventory

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'last_login')
    search_fields = ('name',)

@admin.register(GameSave)
class GameSaveAdmin(admin.ModelAdmin):
    list_display = ('save_name', 'player', 'created_at', 'updated_at')
    list_filter = ('player',)
    search_fields = ('save_name', 'player__name')

@admin.register(GameItem)
class GameItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'item_type')
    list_filter = ('item_type',)
    search_fields = ('name', 'description')

@admin.register(PlayerInventory)
class PlayerInventoryAdmin(admin.ModelAdmin):
    list_display = ('player', 'game_save', 'item', 'quantity')
    list_filter = ('player', 'game_save')
