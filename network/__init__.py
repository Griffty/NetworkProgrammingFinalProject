from network.PlaceTowerPacket import PlaceTowerPacket
from network.configure_pressure_packet import ConfigurePressurePacket
from network.error_packet import ErrorPacket
from network.game_over_packet import GameOverPacket
from network.game_start_packet import GameStartPacket
from network.game_state_packet import GameStatePacket
from network.hello_packet import HelloPacket
from network.packets import PacketRegistry
from network.sell_tower_packet import SellTowerPacket
from network.skip_build_packet import SkipBuildPacket
from network.upgrade_tower_packet import UpgradeTowerPacket
from network.welcome_packet import WelcomePacket


def register_packets() -> None:
    for packet_cls in (
        HelloPacket,
        WelcomePacket,
        PlaceTowerPacket,
        UpgradeTowerPacket,
        SellTowerPacket,
        ConfigurePressurePacket,
        SkipBuildPacket,
        GameStartPacket,
        GameStatePacket,
        GameOverPacket,
        ErrorPacket,
    ):
        if not PacketRegistry.is_registered(packet_cls.packet_id()):
            packet_cls.register()
