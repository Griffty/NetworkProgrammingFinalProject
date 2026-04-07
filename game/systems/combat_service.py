"""Tower attack resolution for active enemies."""

from game.towers.registry import get_tower
from shared.models.state import PlayerState, WaveState

class CombatService:
    """Advance tower cooldowns and apply tower damage to enemies."""

    def update_tower_combat(
        self,
        player: PlayerState,
        wave: WaveState,
        delta_seconds: float,
    ) -> None:
        """Resolve tower attacks for one player during a simulation tick."""

        if not player.towers or not wave.active_enemies:
            return

        for tower in player.towers.values():
            tower.cooldown_seconds = max(0.0, tower.cooldown_seconds - delta_seconds)
            if tower.cooldown_seconds > 0.0:
                continue

            active_enemies = [enemy for enemy in wave.active_enemies if enemy.is_alive]
            if not active_enemies:
                break

            tower_model = get_tower(tower.tower_type)
            shot = tower_model.attack(tower, active_enemies)
            if shot is None:
                continue

            for enemy in shot.hit_enemies:
                enemy.current_hp -= shot.damage

            tower.cooldown_seconds = tower_model.cooldown_seconds(tower)
            self._cleanup_destroyed_enemies(player, wave)

    def _cleanup_destroyed_enemies(self, player: PlayerState, wave: WaveState) -> None:
        """Remove dead enemies and award kill rewards."""

        destroyed_enemies = [enemy for enemy in wave.active_enemies if not enemy.is_alive]
        for enemy in destroyed_enemies:
            wave.active_enemies.remove(enemy)
            wave.killed_enemies += 1
            player.total_kills += 1
            player.gold += enemy.kill_reward
