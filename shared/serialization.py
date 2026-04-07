"""Serialization helpers for match state sent over the network."""

from __future__ import annotations

from game.match_state import MatchState
from shared.models.board import DEFAULT_BOARD_LAYOUT
from shared.models.game_rules import (
    EnemyKind,
    MatchPhase,
    OffensiveModifier,
    TowerKind,
)
from shared.models.state import (
    EnemyState,
    OutgoingPressureState,
    PlayerState,
    TowerState,
    WaveState,
    zero_enemy_counts,
)


def serialize_match_state(state: MatchState) -> dict:
    """Convert a runtime match state into plain JSON-safe data."""

    return {
        "match_id": state.match_id,
        "phase": state.phase.value,
        "current_wave_number": state.current_wave_number,
        "tick_rate_hz": state.tick_rate_hz,
        "tick_count": state.tick_count,
        "elapsed_seconds": state.elapsed_seconds,
        "phase_time_remaining_seconds": state.phase_time_remaining_seconds,
        "players": {
            pid: _serialize_player(p) for pid, p in state.players.items()
        },
        "winner_player_id": state.winner_player_id,
        "is_draw": state.is_draw,
        "recent_events": list(state.recent_events),
    }


def deserialize_match_state(data: dict) -> MatchState:
    """Rebuild a runtime match state from serialized packet data."""

    state = MatchState()
    state.match_id = data["match_id"]
    state.phase = MatchPhase(data["phase"])
    state.current_wave_number = data["current_wave_number"]
    state.tick_rate_hz = data["tick_rate_hz"]
    state.tick_count = data["tick_count"]
    state.elapsed_seconds = data["elapsed_seconds"]
    state.phase_time_remaining_seconds = data["phase_time_remaining_seconds"]
    state.players = {
        pid: _deserialize_player(pid, pdata)
        for pid, pdata in data["players"].items()
    }
    state.winner_player_id = data["winner_player_id"]
    state.is_draw = data["is_draw"]
    state.recent_events = list(data["recent_events"])
    return state


def _serialize_player(player: PlayerState) -> dict:
    """Serialize a player state block."""

    return {
        "name": player.name,
        "gold": player.gold,
        "lives": player.lives,
        "towers": {
            str(tid): _serialize_tower(t) for tid, t in player.towers.items()
        },
        "current_wave": _serialize_wave(player.current_wave),
        "outgoing_pressure": _serialize_pressure(player.outgoing_pressure),
        "ready_for_next_wave": player.ready_for_next_wave,
        "total_kills": player.total_kills,
        "total_leaks_taken": player.total_leaks_taken,
        "completed_waves": player.completed_waves,
    }


def _deserialize_player(player_id: str, data: dict) -> PlayerState:
    """Deserialize a player state block."""

    towers = {
        int(tid): _deserialize_tower(tdata) for tid, tdata in data["towers"].items()
    }
    return PlayerState(
        player_id=player_id,
        name=data["name"],
        gold=data["gold"],
        lives=data["lives"],
        board_layout=DEFAULT_BOARD_LAYOUT,
        towers=towers,
        current_wave=_deserialize_wave(data["current_wave"]),
        outgoing_pressure=_deserialize_pressure(data["outgoing_pressure"]),
        ready_for_next_wave=data["ready_for_next_wave"],
        total_kills=data["total_kills"],
        total_leaks_taken=data["total_leaks_taken"],
        completed_waves=data["completed_waves"],
    )


def _serialize_tower(tower: TowerState) -> dict:
    """Serialize a tower state block."""

    return {
        "tower_id": tower.tower_id,
        "tower_type": tower.tower_type.value,
        "tile_x": tower.tile_x,
        "tile_y": tower.tile_y,
        "level": tower.level,
        "total_gold_spent": tower.total_gold_spent,
        "cooldown_seconds": tower.cooldown_seconds,
    }


def _deserialize_tower(data: dict) -> TowerState:
    """Deserialize a tower state block."""

    return TowerState(
        tower_id=data["tower_id"],
        tower_type=TowerKind(data["tower_type"]),
        tile_x=data["tile_x"],
        tile_y=data["tile_y"],
        level=data["level"],
        total_gold_spent=data["total_gold_spent"],
        cooldown_seconds=data["cooldown_seconds"],
    )


def _serialize_enemy(enemy: EnemyState) -> dict:
    """Serialize an enemy state block."""

    return {
        "enemy_id": enemy.enemy_id,
        "enemy_type": enemy.enemy_type.value,
        "defending_player_id": enemy.defending_player_id,
        "reward_player_id": enemy.reward_player_id,
        "max_hp": enemy.max_hp,
        "current_hp": enemy.current_hp,
        "speed_tiles_per_second": enemy.speed_tiles_per_second,
        "leak_damage": enemy.leak_damage,
        "kill_reward": enemy.kill_reward,
        "distance_travelled_tiles": enemy.distance_travelled_tiles,
        "position_x": enemy.position_x,
        "position_y": enemy.position_y,
    }


def _deserialize_enemy(data: dict) -> EnemyState:
    """Deserialize an enemy state block."""

    return EnemyState(
        enemy_id=data["enemy_id"],
        enemy_type=EnemyKind(data["enemy_type"]),
        defending_player_id=data["defending_player_id"],
        reward_player_id=data["reward_player_id"],
        max_hp=data["max_hp"],
        current_hp=data["current_hp"],
        speed_tiles_per_second=data["speed_tiles_per_second"],
        leak_damage=data["leak_damage"],
        kill_reward=data["kill_reward"],
        distance_travelled_tiles=data["distance_travelled_tiles"],
        position_x=data["position_x"],
        position_y=data["position_y"],
    )


def _serialize_wave(wave: WaveState) -> dict:
    """Serialize a wave state block."""

    return {
        "wave_number": wave.wave_number,
        "base_points": wave.base_points,
        "modifier_budget": wave.modifier_budget,
        "queued_enemies": [_serialize_enemy(e) for e in wave.queued_enemies],
        "active_enemies": [_serialize_enemy(e) for e in wave.active_enemies],
        "spawn_interval_seconds": wave.spawn_interval_seconds,
        "spawn_cooldown_seconds": wave.spawn_cooldown_seconds,
        "spawned_enemies": wave.spawned_enemies,
        "killed_enemies": wave.killed_enemies,
        "leaked_enemies": wave.leaked_enemies,
        "base_unit_counts": {k.value: v for k, v in wave.base_unit_counts.items()},
        "added_unit_counts": {k.value: v for k, v in wave.added_unit_counts.items()},
    }


def _deserialize_wave(data: dict) -> WaveState:
    """Deserialize a wave state block."""

    return WaveState(
        wave_number=data["wave_number"],
        base_points=data["base_points"],
        modifier_budget=data["modifier_budget"],
        queued_enemies=[_deserialize_enemy(e) for e in data["queued_enemies"]],
        active_enemies=[_deserialize_enemy(e) for e in data["active_enemies"]],
        spawn_interval_seconds=data["spawn_interval_seconds"],
        spawn_cooldown_seconds=data["spawn_cooldown_seconds"],
        spawned_enemies=data["spawned_enemies"],
        killed_enemies=data["killed_enemies"],
        leaked_enemies=data["leaked_enemies"],
        base_unit_counts={EnemyKind(k): v for k, v in data["base_unit_counts"].items()},
        added_unit_counts={EnemyKind(k): v for k, v in data["added_unit_counts"].items()},
    )


def _serialize_pressure(pressure: OutgoingPressureState) -> dict:
    """Serialize the outgoing pressure plan."""

    return {
        "unit_counts": {k.value: v for k, v in pressure.unit_counts.items()},
        "modifiers": [m.value for m in pressure.modifiers],
    }


def _deserialize_pressure(data: dict) -> OutgoingPressureState:
    """Deserialize the outgoing pressure plan."""

    return OutgoingPressureState(
        unit_counts={EnemyKind(k): v for k, v in data["unit_counts"].items()},
        modifiers={OffensiveModifier(m) for m in data["modifiers"]},
    )
