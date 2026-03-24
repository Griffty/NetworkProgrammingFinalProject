# Space Legion TD Project Plan

## Goal
Finish a simple, working 2-player competitive tower defense game based on `readme.md`:

- Both players defend against standardized waves.
- Both players can spend resources on defense or offense.
- Players can send extra pressure and modify upcoming waves.
- Matches escalate until one player loses from leaks.

This plan is ordered to keep the project simple and finishable.

## Step-by-step plan

### 1. Lock the MVP rules
Before building more code, write down the first playable version in exact numbers.

- Decide map size and enemy path for each player.
- Decide starting gold, lives, and wave timing.
- Pick a very small content set:
  - 3 tower types
  - 3 enemy types
  - 2 or 3 offensive actions
  - 2 or 3 wave modifiers
- Define leak rules and win condition.
- Define how gold is earned after waves and from sends.

Done when:
- The full match rules fit in one short design doc or config file.

### 2. Build the core game state
Create the headless game logic first, without graphics.

- Add shared models for:
  - match state
  - player state
  - towers
  - enemies
  - waves
  - economy
- Add a fixed game tick/update loop.
- Keep all important game logic server-authoritative.

Done when:
- A match can run in code without any UI.

### 3. Implement the map and movement
Build the tower defense board for one player first.

- Create the placement grid.
- Mark valid and invalid tower cells.
- Add a fixed enemy path.
- Add enemy movement along that path.
- Add leak detection at the end of the path.

Done when:
- Enemies can spawn, move, and leak correctly.

### 4. Implement towers and combat
Add the minimum defense gameplay.

- Place towers on valid cells.
- Give each tower range, attack speed, and damage.
- Add targeting rules.
- Add enemy health and death handling.
- Add simple upgrades and selling.

Done when:
- A player can survive early waves by placing and upgrading towers.

### 5. Implement base waves
Build the standardized wave system from the README.

- Create a wave data format.
- Define wave start, spawn schedule, and wave end.
- Scale base wave difficulty over time.
- Add a short build phase between waves.

Done when:
- Multiple waves can run from start to finish in sequence.

### 6. Implement economy and resource decisions
Build the defense-vs-offense economy loop.

- Give players gold at the right times.
- Charge gold for tower placement and upgrades.
- Add income changes if your design needs them.
- Show enough state to understand spending decisions.

Done when:
- The player must choose between saving, defending, and attacking.

### 7. Implement loss and match flow
Finish the basic single-match loop.

- Reduce lives or health on leaks.
- End the match when a player reaches the loss condition.
- Add restart and return-to-menu flow.

Done when:
- One full offline match can start, progress, and end cleanly.

### 8. Expand networking from handshake to gameplay commands
Use the current client/server scaffold as the base.

- Add packets for:
  - join match
  - ready/start
  - place tower
  - upgrade tower
  - sell tower
  - send offense
  - apply wave modifier
- Add authoritative server validation for every action.
- Add state/event packets from server to clients.

Done when:
- The server owns the real match state and clients only send commands.

### 9. Sync a full 2-player match
Move from one-player simulation to competitive play.

- Run both players inside the same authoritative match.
- Give each player their own board, gold, lives, and tower state.
- Make base waves hit both players.
- Make sends and modifiers affect the opponent.
- Keep both clients updated with the correct state.

Done when:
- Two connected clients can complete a real match together.

### 10. Add the offensive system
Implement the attack side of the game in a minimal but useful form.

- Add extra enemy sends.
- Charge gold for sends.
- Spawn sent enemies into the opponent's next wave or active queue.
- Show the incoming pressure to the defender.

Done when:
- Players can punish weak defenses by spending on offense.

### 11. Add wave manipulation
Implement the mind-game layer from the README.

- Add wave modifiers such as:
  - more tanks
  - more swarm units
  - faster units
  - armored or shielded units
  - denser spawns
- Decide whether modifiers affect the next wave only or stack.
- Balance costs and limits.

Done when:
- Players can deliberately target likely weaknesses in the opponent's build.

### 12. Add damage types, resistances, and tower roles
This is where the tower strategy becomes more interesting.

- Add damage categories.
- Add enemy resistances or armor traits.
- Make towers fill distinct jobs:
  - single target
  - area damage
  - anti-fast
  - economy/greed

Done when:
- Tower composition matters, not just raw damage.

### 13. Add escalation and unlock pacing
Make matches build toward a breaking point.

- Increase wave strength over time.
- Unlock stronger offensive tools later in the match.
- Unlock stronger tower upgrades later if needed.
- Prevent early all-in strategies from ending every match immediately.

Done when:
- Matches have early, mid, and late-game pressure.

### 14. Build the minimal UI
Keep it simple and readable.

- Main menu: host, connect, quit.
- In-match HUD:
  - gold
  - lives
  - wave number
  - build buttons
  - offense buttons
  - basic opponent summary
- Show placement range and valid cells.
- Show wave start/end and win/loss states.

Done when:
- A new player can understand how to start and play a match.

### 15. Add content and data cleanup
Move hardcoded values into data where possible.

- Store tower stats in data files.
- Store enemy stats in data files.
- Store wave definitions in data files.
- Make balancing changes easy without rewriting code.

Done when:
- Most tuning can be done through config/data instead of code changes.

### 16. Test and balance the core loop
Do repeated playtests before adding more features.

- Test tower costs and strength.
- Test send costs and pressure timing.
- Test whether wave modifiers are readable and fair.
- Test if matches end too quickly or drag too long.
- Fix desync, invalid actions, and edge cases.

Done when:
- The game is stable and the main decisions feel meaningful.

### 17. Add polish only after the game works
Only do the small polish items that improve usability.

- Better feedback for hits, leaks, and sends.
- Cleaner text and button labels.
- Better error handling for disconnects.
- Basic sound if time allows.

Done when:
- The game feels clear and complete, even if visually simple.

### 18. Optional online features after the core game is finished
Do not block the project on this.

- Dedicated server mode using the same server logic.
- Simple server list or direct IP join improvements.
- Optional master server for matchmaking later.

Done when:
- Online access is more convenient, but not required for the core game to exist.

## Suggested milestone order

### Milestone 1: Offline prototype
Finish steps 1 through 7.

Result:
- One local player can play a full simple tower defense match.

### Milestone 2: Networked core match
Finish steps 8 and 9.

Result:
- Two players can connect and play the same match with server authority.

### Milestone 3: Competitive depth
Finish steps 10 through 13.

Result:
- The game includes defense, offense, wave manipulation, and escalation.

### Milestone 4: Finish and ship
Finish steps 14 through 17.

Result:
- The game is complete, readable, stable, and ready for normal playtesting.

## Definition of done
The project is finished when:

- Two players can host/connect and complete a full match.
- Both defense and offense are meaningful every wave.
- Wave manipulation works and changes real outcomes.
- Matches escalate naturally and end through leaks.
- The server is authoritative and stable.
- The UI is simple but clear enough to play without guessing.
