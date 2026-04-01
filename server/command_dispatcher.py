from __future__ import annotations

from game.commands import (
    ConfigurePressureCommand,
    GameCommand,
    PlaceTowerCommand,
    SellTowerCommand,
    SkipBuildCommand,
    UpgradeTowerCommand,
)
from network.configure_pressure_packet import ConfigurePressurePacket
from network.place_tower_packet import PlaceTowerPacket
from network.sell_tower_packet import SellTowerPacket
from network.skip_build_packet import SkipBuildPacket
from network.upgrade_tower_packet import UpgradeTowerPacket
from shared.models.game_rules import EnemyKind, OffensiveModifier, TowerKind


class ServerCommandDispatcher:
    def parse_packet(self, packet: object) -> GameCommand:
        if isinstance(packet, PlaceTowerPacket):
            return PlaceTowerCommand(
                tower_type=TowerKind(packet.tower_type),
                tile_x=packet.tile_x,
                tile_y=packet.tile_y,
            )

        if isinstance(packet, UpgradeTowerPacket):
            return UpgradeTowerCommand(tower_id=packet.tower_id)

        if isinstance(packet, SellTowerPacket):
            return SellTowerCommand(tower_id=packet.tower_id)

        if isinstance(packet, ConfigurePressurePacket):
            unit_counts = {
                EnemyKind(enemy_kind): count
                for enemy_kind, count in packet.unit_counts.items()
            }
            modifiers = {OffensiveModifier(modifier) for modifier in packet.modifiers}
            return ConfigurePressureCommand(
                unit_counts=unit_counts,
                modifiers=modifiers,
            )

        if isinstance(packet, SkipBuildPacket):
            return SkipBuildCommand()

        raise ValueError(f"Unsupported packet: {type(packet).__name__}")

