from network.PlaceTowerPacket import PlaceTowerPacket
from network.hello_packet import HelloPacket
from network.packets import PacketRegistry
from network.welcome_packet import WelcomePacket


def register_packets() -> None:
    for packet_cls in (HelloPacket, WelcomePacket, PlaceTowerPacket):
        if not PacketRegistry.is_registered(packet_cls.packet_id()):
            packet_cls.register()
