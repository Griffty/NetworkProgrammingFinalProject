import argparse
import threading
import time

from client.game_client import GameClient
from game.systems import MatchEngine
from server.game_server import GameServer
from shared.settings import DEFAULT_HOST, DEFAULT_PORT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Space Legion TD networking scaffold")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    server_parser = subparsers.add_parser("server", help="Run the local game server")
    server_parser.add_argument("--host", default=DEFAULT_HOST)
    server_parser.add_argument("--port", default=DEFAULT_PORT, type=int)

    client_parser = subparsers.add_parser("client", help="Connect a test client")
    client_parser.add_argument("--host", default=DEFAULT_HOST)
    client_parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    client_parser.add_argument("--name", default="Player1")

    local_test_parser = subparsers.add_parser(
        "local-test", help="Start a local server and connect one test client"
    )
    local_test_parser.add_argument("--host", default=DEFAULT_HOST)
    local_test_parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    local_test_parser.add_argument("--name", default="Player1")

    simulate_parser = subparsers.add_parser(
        "simulate-match", help="Run the headless match state for testing"
    )
    simulate_parser.add_argument("--seconds", default=30.0, type=float)
    simulate_parser.add_argument("--player1", default="Player1")
    simulate_parser.add_argument("--player2", default="Player2")

    gui_parser = subparsers.add_parser(
        "gui", help="Launch a pygame viewer for the current simulation"
    )
    gui_parser.add_argument("--player1", default="Player1")
    gui_parser.add_argument("--player2", default="Player2")
    gui_parser.add_argument("--auto-quit-seconds", type=float)

    play_parser = subparsers.add_parser(
        "play", help="Connect to a server and play with pygame"
    )
    play_parser.add_argument("--host", default=DEFAULT_HOST)
    play_parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    play_parser.add_argument("--name", default="Player1")

    return parser


def run_server(host: str, port: int) -> None:
    server = GameServer(host=host, port=port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()


def run_client(host: str, port: int, name: str) -> None:
    client = GameClient(host=host, port=port, player_name=name)
    client.connect()


def run_local_test(host: str, port: int, name: str) -> None:
    server = GameServer(host=host, port=port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Give the server a brief moment to bind before connecting.
    time.sleep(0.2)

    try:
        client = GameClient(host=host, port=port, player_name=name)
        client.connect()
    finally:
        server.stop()
        server_thread.join(timeout=1.0)


def run_simulation(seconds: float, player1: str, player2: str) -> None:
    engine = MatchEngine(player_names=[player1, player2])
    engine.advance(seconds)

    print("Headless match summary")
    for line in engine.summary_lines():
        print(line)

    print("\nRecent events")
    for event in engine.state.recent_events[-10:]:
        print(event)


def run_gui(player1: str, player2: str, auto_quit_seconds: float | None) -> None:
    try:
        from client.pygame_client import PygameSimulationClient
    except ModuleNotFoundError as error:
        if error.name == "pygame":
            raise SystemExit(
                "pygame is not installed for this interpreter. "
                "Use the project venv, for example: .venv/bin/python main.py gui"
            ) from error
        raise

    viewer = PygameSimulationClient(
        player1_name=player1,
        player2_name=player2,
        auto_quit_seconds=auto_quit_seconds,
    )
    viewer.run()


def run_play(host: str, port: int, name: str) -> None:
    try:
        from client.pygame_network_client import PygameNetworkClient
    except ModuleNotFoundError as error:
        if error.name == "pygame":
            raise SystemExit(
                "pygame is not installed for this interpreter. "
                "Use the project venv, for example: .venv/bin/python main.py play"
            ) from error
        raise

    client = PygameNetworkClient(host=host, port=port, player_name=name)
    client.run()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "server":
        run_server(args.host, args.port)
    elif args.mode == "client":
        run_client(args.host, args.port, args.name)
    elif args.mode == "simulate-match":
        run_simulation(args.seconds, args.player1, args.player2)
    elif args.mode == "gui":
        run_gui(args.player1, args.player2, args.auto_quit_seconds)
    elif args.mode == "play":
        run_play(args.host, args.port, args.name)
    else:
        run_local_test(args.host, args.port, args.name)


if __name__ == "__main__":
    main()
