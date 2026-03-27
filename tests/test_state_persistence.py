import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import create_mock_character


class TestStatePersistence:
    def test_nonpersistable_state_is_not_saved(self, mock_game_state):
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateForcedSitting

        actor = create_mock_character()
        state = CharacterStateForcedSitting(actor=actor, game_state=mock_game_state, source_actor=actor)
        state.tick_started = 100
        state.tick_ending = 120

        assert state.save_state() is None

    def test_experience_modifier_save_uses_remaining_duration(self, mock_game_state):
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateExperienceModifier

        actor = create_mock_character()
        state = CharacterStateExperienceModifier(
            actor=actor,
            game_state=mock_game_state,
            source_actor=None,
            state_type_name="perspicacious",
            modifier=2.5,
        )
        state.tick_started = 100
        state.tick_ending = 140

        saved = state.save_state()

        assert saved["class"] == "CharacterStateExperienceModifier"
        assert saved["remaining_duration_ticks"] == 40
        assert saved["modifier"] == 2.5
        assert saved["state_type_name"] == "perspicacious"

    @pytest.mark.asyncio
    async def test_load_state_restores_experience_modifier_silently(self, mock_game_state):
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateExperienceModifier, load_state_from_data

        actor = create_mock_character()
        actor.states = []
        actor.apply_state = MagicMock(side_effect=lambda state: actor.states.append(state))
        actor.echo = AsyncMock()

        restored = await load_state_from_data(actor, mock_game_state, {
            "class": "CharacterStateExperienceModifier",
            "duration": 60,
            "state_type_name": "perspicacious",
            "modifier": 1.5,
        })

        assert isinstance(restored, CharacterStateExperienceModifier)
        assert restored.modifier == 1.5
        assert restored.tick_ending == 220
        actor.echo.assert_not_awaited()
        assert actor.states == [restored]

    @pytest.mark.asyncio
    async def test_max_hp_state_apply_and_remove_clamps_current_hp(self, mock_game_state):
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateMaxHpBonus

        actor = create_mock_character(hp=80, max_hp=100, is_pc=True)
        actor.states = []
        actor.apply_state = MagicMock(side_effect=lambda state: actor.states.append(state))
        actor.remove_state = MagicMock(return_value=True)
        actor.echo = AsyncMock()
        actor.send_status_update = AsyncMock()

        state = CharacterStateMaxHpBonus(
            actor=actor,
            game_state=mock_game_state,
            source_actor=None,
            state_type_name="fortified",
            affect_amount=20,
        )

        await state.apply_state(start_tick=100, duration_ticks=20)
        assert actor.max_hit_points == 120
        assert actor.current_hit_points == 80
        actor.send_status_update.assert_awaited()

        actor.current_hit_points = 115
        await state.remove_state()
        assert actor.max_hit_points == 100
        assert actor.current_hit_points == 100

    @pytest.mark.asyncio
    async def test_load_state_restores_max_hp_silently_and_updates_status(self, mock_game_state):
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateMaxHpBonus, load_state_from_data

        actor = create_mock_character(hp=80, max_hp=100, is_pc=True)
        actor.states = []
        actor.apply_state = MagicMock(side_effect=lambda state: actor.states.append(state))
        actor.echo = AsyncMock()
        actor.send_status_update = AsyncMock()

        restored = await load_state_from_data(actor, mock_game_state, {
            "class": "CharacterStateMaxHpBonus",
            "remaining_duration_ticks": 25,
            "state_type_name": "fortified",
            "affect_amount": 20,
        })

        assert isinstance(restored, CharacterStateMaxHpBonus)
        assert actor.max_hit_points == 120
        assert actor.current_hit_points == 80
        assert restored.tick_ending == 125
        actor.echo.assert_not_awaited()
        actor.send_status_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_load_charmed_without_resolvable_charmer_becomes_confused(self, mock_game_state):
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateConfused, load_state_from_data
        from NextGenMUDApp.nondb_models.character_interface import TemporaryCharacterFlags

        actor = create_mock_character(hp=80, max_hp=100, is_pc=True)
        actor.states = []
        actor.apply_state = MagicMock(side_effect=lambda state: actor.states.append(state))
        actor.echo = AsyncMock()
        actor.send_status_update = AsyncMock()
        actor.charmed_by = None
        actor.add_temp_flags = MagicMock(side_effect=lambda flags: setattr(
            actor, "temporary_character_flags", actor.temporary_character_flags.add_flags(flags)
        ) or True)
        actor.remove_temp_flags = MagicMock(side_effect=lambda flags: setattr(
            actor, "temporary_character_flags", actor.temporary_character_flags.remove_flags(flags)
        ) or True)

        restored = await load_state_from_data(actor, mock_game_state, {
            "class": "CharacterStateCharmed",
            "remaining_duration_ticks": 12,
            "state_type_name": "charmed",
            "charmed_by_reference": "C999",
            "charmed_by_id": "missing_charmer",
            "charmed_by_name": "Missing Charmer",
        })

        assert isinstance(restored, CharacterStateConfused)
        assert actor.has_temp_flags(TemporaryCharacterFlags.IS_CONFUSED)
        assert getattr(actor, "charmed_by", None) is None
        actor.echo.assert_not_awaited()
