# Space Legion TD MVP Design Doc

## Goal
Build a simple 2-player competitive tower defense game with:

- fixed tower placement
- standardized base waves
- player-controlled offensive pressure
- minimal vector-style visuals
- server-authoritative multiplayer

This document locks the first playable version. Balance numbers can change later.

## Presentation

- Graphics style: very minimal vector shapes only
- No detailed sprites or animation-heavy effects
- Towers, enemies, projectiles, and UI should be readable first
- Suggested style:
  - towers are simple colored shapes
  - enemies are simple colored shapes with small health bars
  - railgun uses a straight beam line
  - splash attacks use circles
  - path/build grid uses flat colors

## Match Structure

- Players: 2
- Each player has their own separate board
- Both players receive the same base wave each round
- Both players can spend gold on defense or on pressure for the opponent
- A player loses when their lives reach 0

## Map Rules

- Map size: 64 x 64 tiles per player board
- Tile system: square grid
- Pathing: fixed prebuilt path, not dynamic pathfinding for MVP
- Each board uses the same path layout for fairness
- Enemy spawn point: left side of the map
- Leak point: right side of the map
- Tower placement: only on buildable tiles, never on path tiles
- Tower size: 1 x 1 tile for MVP

## Core Match Values

- Starting gold: 100
- Starting lives: 25
- Wave delay: next wave starts 20 seconds after the current wave is fully cleared for both players
- Sell refund: 70 percent of total gold spent on that tower
- Upgrade system: each tower has base level plus 2 upgrades

## Enemy Types

There are 3 base enemy types for the MVP. They are also the unit types used by the wave-modifier sliders.

### 1. Runner
- Role: fast, low HP, swarm pressure
- Point cost: 1
- Base HP: 20
- Speed: fast
- Leak damage: 1
- Kill reward: 1 gold

### 2. Brute
- Role: slow, high HP tank
- Point cost: 3
- Base HP: 70
- Speed: slow
- Leak damage: 2
- Kill reward: 3 gold

### 3. Guard
- Role: medium speed armored unit
- Point cost: 4
- Base HP: 90
- Speed: medium
- Leak damage: 3
- Kill reward: 4 gold

## Enemy Scaling

- Base wave points on wave 1: 30
- Base wave points increase by 8 each wave
- Enemy HP scales by 10 percent per wave
- Enemy leak damage does not scale every wave, but later tougher units already deal more leak damage

Formula:

- `base_wave_points = 30 + ((wave_number - 1) * 8)`
- `enemy_hp_multiplier = 1.0 + ((wave_number - 1) * 0.10)`

## Tower Types

There are 3 towers in the MVP. Their exact balance can be changed later, but their roles should stay distinct.

### 1. Minigun Tower
- Role: fast shooting, low range, strong against runners
- Cost: 35 gold
- Range: 5 tiles
- Damage: 4
- Attack speed: 5 shots per second
- Targeting: first enemy in range
- Upgrade focus: more fire rate and damage

### 2. Railgun Tower
- Role: long-range anti-line tower
- Cost: 60 gold
- Range: 12 tiles
- Damage: 35
- Attack speed: 0.7 shots per second
- Special: beam penetrates every enemy in a straight line
- Upgrade focus: more damage and beam width

### 3. Pulse Tower
- Role: anti-swarm splash damage
- Cost: 50 gold
- Range: 7 tiles
- Damage: 14
- Attack speed: 1.2 shots per second
- Special: small area blast on hit
- Splash radius: 1.5 tiles
- Upgrade focus: larger splash and more damage

## Damage and Targeting Rules

- Towers can only attack enemies on their own board
- For MVP, all damage is direct and simple
- No resistances in the first playable build
- Targeting priority for all towers starts as:
  - first
  - closest to exit
- Extra targeting modes can be added later if needed

## Wave System

- Each wave has a standardized base composition generated from the wave point budget
- The first waves should be runner-heavy
- Later waves should add more brutes and guards
- Base wave composition should be predictable enough for players to plan around

Suggested default base composition rules:

- Wave 1 to 2: mostly runners
- Wave 3 to 4: runners plus some brutes
- Wave 5 and later: runners, brutes, and guards

## Player Offensive System

Each player can pressure the opponent during the build phase before the next wave.

### Offensive modifiers

Players can buy these effects for the opponent's next wave:

#### 1. Reinforce
- Effect: all added enemy units gain 25 percent more HP
- Cost: 12 gold
- Limit: once per wave

#### 2. Haste
- Effect: all added enemy units gain 20 percent move speed
- Cost: 12 gold
- Limit: once per wave

#### 3. Reinforcements
- Effect: gain 10 extra modifier points for the next wave
- Cost: 15 gold
- Limit: once per wave

## Wave Modifier Slider System

Players also get a point budget to shape the extra pressure sent to the opponent.

- Wave 1 modifier budget: 20 points
- Modifier budget each wave: 66 percent of the base wave point total, rounded down
- Modifier budget only affects the opponent's next wave
- Players split the budget across Runner, Brute, and Guard sliders
- Players cannot exceed the point budget
- Unused modifier points are lost

Formula:

- `modifier_points = floor(base_wave_points * 0.66)`

Example for wave 1:

- base wave points = 30
- modifier points = 20
- player could send:
  - 20 runners
  - 6 brutes and 2 runners
  - 5 guards
  - any other valid combination

## Economy Rules

Players earn gold from 3 sources:

### 1. Enemy kills
- Kill reward is based on the enemy type
- Runner: 1 gold
- Brute: 3 gold
- Guard: 4 gold

### 2. Wave clear bonus
- Every time a player survives a wave, they gain bonus gold
- Formula:
  - `wave_clear_bonus = 20 + (wave_number * 5)`

### 3. Opponent leaks
- If the opponent leaks enemies, the player gains gold
- Leak reward equals the life damage dealt by the leaking enemy
- This applies whether the pressure came from the base wave or player modifications

Example:

- a leaked Runner gives the opponent 1 gold
- a leaked Brute gives the opponent 2 gold
- a leaked Guard gives the opponent 3 gold

## Leak and Loss Rules

- A leak happens when an enemy reaches the end of the path
- The defending player loses lives equal to that enemy's leak damage
- If a player's lives reach 0, they lose immediately
- If both players reach 0 lives on the same server tick, the match is a draw

## Build Phase Rules

- After both players clear the current wave, a 20-second build phase starts
- During the build phase, players can:
  - build towers
  - upgrade towers
  - sell towers
  - buy offensive modifiers
  - set slider values for the next wave
- When the timer ends, the next wave starts automatically

## UI Rules

The MVP UI should stay simple.

- Show your gold
- Show your lives
- Show current wave
- Show build phase timer
- Show tower buttons with cost
- Show offensive buttons with cost
- Show slider controls for Runner, Brute, and Guard
- Show a small summary of the opponent:
  - lives
  - gold
  - wave status

## Implementation Notes

- Server is authoritative for all match state
- Clients send commands only
- Use shared config/data files for tower and enemy values as early as possible
- Keep visuals minimal so implementation time goes into gameplay
- Make all balance values easy to edit later

## What counts as the first playable version

The MVP is playable when:

- 2 players can join the same match
- both players can place, upgrade, and sell towers
- waves spawn and progress correctly
- kills give gold
- leaks remove lives
- wave clear gives bonus gold
- offensive modifiers and slider-based added units work
- one player can lose and the other can win
