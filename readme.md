# Space Legion TD

A simple 2-player competitive tower defense prototype built with Python and `pygame`.

Both players defend their own board while sending pressure to the opponent. The server runs the simulation, and clients render the game state + send player commands.

## Features

- Real-time client/server multiplayer (TCP sockets)
- Build and wave phases
- 64x64 tile map with fixed pathing
- 3 tower types:
  - `Minigun`: fast, low range, single target
  - `Railgun`: slow beam, long range, penetrates
  - `Pulse`: medium attack speed, splash damage
- Offensive pressure planning:
  - Add units (`Runner`, `Brute`, `Guard`)
  - Apply modifiers (`Reinforce`, `Haste`, `Reinforcements`)
- Economy loop:
  - Gold from kills
  - Wave clear bonus
  - Leak reward to attacker
- Match end + post-match UI flow (play again / exit)
- Resizable lobby and game views

## Tech Stack

- Python
- `pygame` for client rendering/input
- Custom packet protocol over TCP sockets
- Authoritative server simulation

## Project Layout

```text
client/      pygame UI + network client
server/      socket server, lobby, match runner
game/        match state + systems (build/combat/wave/phase/pressure)
network/     packet definitions + codec registration
shared/      shared models, rules, serialization, settings
main.py      CLI entrypoint (server/client)
```

## Game Rules (Current Defaults)

- Map: `64 x 64`
- Starting gold: `100`
- Starting lives: `25`
- Build phase duration: `20s`
- Tick rate: `20 Hz`
- Max players: `2`

## Controls (Client)

- `Left Click` on your board: place selected tower
- `Right Click` on your board: sell tower
- `1 / 2 / 3`: select tower (`Minigun / Railgun / Pulse`)
- `Space`: ready/skip build phase
- Pressure hotkeys:
  - Unit counts: `Q/A` runner `+/-`, `W/S` brute `+/-`, `E/D` guard `+/-`
  - Modifiers: `Z` reinforce, `X` haste, `C` reinforcements

## Running Locally

### 1. Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install pygame
```

### 2. Start Server

```bash
python main.py server --host 0.0.0.0 --port 5000
```

### 3. Start Client(s)

```bash
python main.py client --host 127.0.0.1 --port 5000
```

You can also run the simple launcher:

```bash
python start_client.py
```

Note: host/port from CLI are just initial defaults in lobby fields; you can change them in the UI before connecting.

## LAN Play

1. Host starts server on `0.0.0.0`.
2. Other player connects to host machine LAN IP (for example `192.168.x.x`) and port `5000`.
3. Ensure firewall allows inbound TCP on that port.

## Packaging

Project includes a `start_client.spec` for PyInstaller.

```bash
pyinstaller --noconfirm start_client.spec
```

Built client binary appears in `dist/start_client` (platform-specific behavior applies).

## Prebuilt Clients

Prebuilt client binaries for selected commits are published on GitHub.

- Check the repository **Releases** page for commit-specific builds.
- Pick the artifact that matches your OS.
- Prefer matching client/server builds from the same commit to avoid protocol/version mismatch.

## Networking Notes

- Protocol is plain TCP with custom packets.
- Client/server versions should match.
- Tailscale Funnel public endpoints use TLS; plain TCP client will not connect unless TLS is handled or users are in the same tailnet.

## Current Scope / Limitations

- No persistence/account system
- No replay/spectator mode
- No anti-cheat or authoritative reconciliation beyond current server model
- Gameplay balance is still in progress

## License

No license file is currently included.
