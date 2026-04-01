import argparse

from server.game_server import GameServer
from shared.settings import DEFAULT_HOST, DEFAULT_PORT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Space Legion TD network prototype")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    server_parser = subparsers.add_parser("server", help="Run the game server")
    server_parser.add_argument("--host", default=DEFAULT_HOST)
    server_parser.add_argument("--port", default=DEFAULT_PORT, type=int)

    client_parser = subparsers.add_parser("client", help="Run the pygame client")
    client_parser.add_argument("--host", default=DEFAULT_HOST)
    client_parser.add_argument("--port", default=DEFAULT_PORT, type=int)

    return parser


def run_server(host: str, port: int) -> None:
    server = GameServer(host=host, port=port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()


def run_client(host: str, port: int) -> None:
    try:
        from client.pygame_client import PygameClient
    except ModuleNotFoundError as error:
        if error.name == "pygame":
            raise SystemExit(
                "pygame is not installed for this interpreter. "
                "Use the project venv, for example: .venv/bin/python main.py client"
            ) from error
        raise

    client = PygameClient(host=host, port=port)
    client.run()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "server":
        run_server(args.host, args.port)
    elif args.mode == "client":
        run_client(args.host, args.port)
    else:
        raise ValueError(f"Unsupported mode: {args.mode}")


if __name__ == "__main__":
    main()
