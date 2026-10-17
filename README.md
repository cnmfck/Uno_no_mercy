# UNO No Mercy — Python LAN Card Game

A desktop card game inspired by UNO Show 'em No Mercy, built with Python and Tkinter. Play against bots or host a local-network room for friends, with animated cards, stacking draw penalties, hand swaps, and custom elimination rules.

**2–6 players · Python 3.10+ · No third-party Python dependencies · Network protocol v6**

The current game interface, in-game messages, and many source comments are in Simplified Chinese. This README is in English. This is an unofficial learning project with custom rules and Canvas-drawn artwork.

## Features

- **Solo practice and LAN multiplayer:** play against 1–5 bots or combine human players and bots in one room.
- **168-card starting deck:** number cards, draw penalties, skips, reverses, hand swaps, and color roulette.
- **Interactive table:** double-click or drag cards to play, hover to inspect cards, and drag a 7 directly onto another player's avatar to swap hands.
- **Animated feedback:** dealing and drawing effects, a color-selection wheel, stacking-penalty displays, elimination effects, and a results podium.
- **Custom round endings:** players who empty their hands finish and leave active play; the remaining players continue until the host's chosen threshold is reached.
- **Reconnect support:** disconnected players can reclaim their seats from the same application window, or the host can assign their seats to bots.
- **Separate game engine, networking, and presentation:** the rules can be tested without opening the GUI.

## Quick Start

Download and extract the repository, then open the folder containing `main.py`.

You need Python 3.10 or newer, Tkinter/Tcl-Tk, and a graphical desktop. There are no packages to install with `pip`; `requirements.txt` is informational.

### Windows

Double-click `start_windows.bat`, or run:

```powershell
py -3 main.py
```

If the Python launcher is unavailable, use `python main.py`.

### macOS / Linux

```bash
python3 main.py
```

Alternatively:

```bash
sh start_unix.sh
```

If Tkinter is missing, install the Tcl/Tk support appropriate for your Python distribution. A terminal-only environment cannot display the game.

## Start a Game

### Practice with bots

1. Enter a nickname in the lobby.
2. Choose 1–5 computer opponents in the left panel and press the practice button below the selector.
3. Set the number of active players remaining when the round should end.
4. Press the start-game button at the table.

### Play over a local network

1. Each player launches the same version of the application on their own computer.
2. The host creates a LAN room using the left lobby panel.
3. The host shares the displayed LAN IPv4 address, port, and six-digit room code.
4. Friends enter those values in the right lobby panel and join the room.
5. The host adds bots if desired, sets the round-ending threshold, and starts the game with 2–6 total players.

The default port is **8765**. Use `127.0.0.1` only when running multiple clients on the same computer. Other computers need the host's LAN address. All clients must use **protocol version 6**.

Devices must be able to reach one another. Guest Wi-Fi, campus networks, and some hotspots isolate connected devices. Allow Python through the host's firewall on the appropriate trusted network if necessary.

## Controls

| Action | Control |
| --- | --- |
| Play a card | Double-click it, or drag it onto the central discard pile. |
| Inspect a card | Hover over it to enlarge it and display its description. |
| Identify playable cards | Look for the gold outline; unavailable cards are dimmed. |
| Draw normally | Click the draw pile on the right when no card can be played. |
| Accept a draw penalty | Click the central penalty prompt when no stacking card is available. |
| Swap hands with a 7 | Drag it onto an active opponent's avatar, or play it centrally and select a target. |
| Choose a wild-card color | Click a color-wheel sector, or use the arrow keys and Enter. |
| Call UNO | Click `UNO!` or press Space. Space still types normally inside text fields. |
| Declare UNO while playing | Enable the checkbox below the UNO button. |
| Catch a missed UNO call | Use the catch button shown beside an eligible opponent. |
| Inspect the game log | Toggle the log panel from the top toolbar. |

## Rules in This Implementation

Each player starts with seven cards. Outside a penalty chain, a card must match the active color or the top card's kind/number, or be a wild card.

### Drawing and stacking

- If you have a playable card, you must play. Otherwise, draw **one card**. If that card is playable, you must play it; otherwise, your turn ends.
- A draw penalty can be stacked with a draw card whose value is at least as large as the **last draw card played**. Color does not restrict stacking.
- For example, `+4 → +6 → +6` is valid and creates a total penalty of 16 cards.
- Taking the accumulated penalty ends your turn and clears the chain.

### Special cards

| Card | Effect |
| --- | --- |
| 7 | Exchange your hand with another active player. |
| 0 | Pass every active player's hand to the next player in the current direction. |
| Skip | Skip the next active player. |
| Reverse | Reverse the direction of play. With two active players, play returns to you. |
| Discard All | Discard your other cards of the same color; those additional cards do not trigger their effects. |
| Skip Everyone | Take another turn. |
| Draw 2 / Draw 4 | Add 2 or 4 cards to the draw-penalty chain. |
| Wild Reverse Draw 4 | Choose a color, reverse direction, and add 4 to the penalty. With two active players, the penalty returns to you and may be stacked. |
| Wild Draw 6 / Wild Draw 10 | Choose a color and add 6 or 10 to the penalty. |
| Wild Color Roulette | Choose a color. The next player draws face-up until drawing that color, then loses their turn. Wild cards do not count as a match. |

If your final card is a 0 or 7, you finish without passing or swapping an empty hand. Other final-card effects still apply.

### UNO calls

Call UNO when you have one card left, or enable the declaration checkbox before playing down to one card. Another player can catch a missed call for a two-card penalty before the next valid play, draw, or roulette color action is accepted.

### Elimination and ranking

Reaching **36 cards** eliminates a player immediately. Drawing stops at elimination, and any unfulfilled portion of that penalty is discarded.

Emptying your hand records a finish and removes you from active play. Before each round, the host chooses an ending threshold from 1 to the total player count minus 1. For example, a four-player round with a threshold of two ends when only two players remain active.

Final ranking follows this order:

1. Players who emptied their hands, in finishing order.
2. Remaining active players, ordered by fewest cards, with ties sharing a rank.
3. Eliminated players, with later eliminations ranked higher.

Room scores accumulate across rounds, with points awarded to the first-place player. There is no automatic 1,000-point match ending. The 36-card limit, continuing play after a finish, and single-card normal draws are custom rules for this project.

## Bots

Bots use a fixed heuristic policy with a configured 1.5-second delay between actions; animation waits can add time. They prioritize Discard All, beneficial hand swaps, and playable colored cards, generally retaining wild cards. They select the most common color in their own hand and the smallest active opponent hand for a 7 swap.

Bots use their own cards and public game information. They do not inspect opponents' card faces, predict deck order, or search future turns.

## Author Mode

Using the nickname **`admin`** or **`op`** enables author mode, ignoring capitalization and surrounding whitespace. This is a nickname-based gameplay feature available to any player who chooses one of those names; it does not grant room-host controls.

- Play any card from your hand, including outside your turn, without normal matching or stacking restrictions.
- Playing a non-draw card clears the current penalty chain; draw cards continue adding to it.
- Right-click your hand area or the table to generate a Wild Reverse Draw 4, Wild Draw 6, Wild Draw 10, or Wild Color Roulette card.
- Cards and avatars receive gold visual effects.
- Normal card effects, animation waits, finishing, and the 36-card elimination limit still apply.

Generated cards have unique identifiers and increase the round's total card count. Use other nicknames for ordinary play.

## Networking and Limitations

The host runs an authoritative TCP server using newline-delimited JSON. Each client receives its own hand and public table state; opponents' unrevealed card faces and deck order are excluded.

- An active human player's disconnect pauses the round. Reconnect from the original window to recover that seat.
- Closing the application loses its in-memory reconnect credentials.
- The host can permanently replace a disconnected guest with a bot.
- The room closes when the host exits. There is no host migration or saved-session recovery.
- Disconnect detection relies on TCP; sudden network loss may take time to register.
- Networking is intended for **trusted local networks**. It has no TLS, account system, public matchmaking, or comprehensive hostile-client protection. Do not expose the server directly to the public internet.
- Windows uses an additional transparent animation overlay. macOS and Linux use a table-contained fallback. Visual behavior needs platform-specific desktop testing.

## Project Structure

| Path | Purpose |
| --- | --- |
| `main.py` | Application entry point, lobby, table interactions, and UI event handling. |
| `engine.py` | Deck creation, rule validation, bot decisions, elimination, and ranking. |
| `network.py` | TCP room server, clients, private state snapshots, and reconnect handling. |
| `card_art.py` | Canvas card artwork and central drop-zone geometry. |
| `color_wheel.py` | Wild-card color-selection interface. |
| `effects.py` | Card movement and other interface effects. |
| `visuals.py` | Table rendering, penalty chains, particles, and podium graphics. |
| `tests/` | Rule, network, rendering, and GUI smoke tests. |
| `check_environment.py` | Interactive Python, Tk, display, and local-address diagnostics. |
| `TEST_REPORT.md` | Test results and manual verification limits. |

## Testing and Troubleshooting

Run the test suite from the project root:

```bash
python -m unittest discover -s tests -v
```

Use `python3` on systems where that is the Python executable. The suite includes randomized games and local TCP integration tests. A real Tk window smoke test skips when no graphical display is available.

For startup problems, run:

```bash
python check_environment.py
```

| Problem | Check |
| --- | --- |
| Tkinter cannot be imported | Install Tcl/Tk support for the Python interpreter you are using. |
| The window cannot open | Run in a graphical desktop session with a working display. |
| A friend cannot connect | Check the host's LAN address, port, firewall, and network isolation. |
| Room code or version is rejected | Recheck the six-digit code and use the same v6 build on every device. |
| The round is paused | Reconnect the missing active player or have the host assign their seat to a bot. |

## Project Notice

This is an unofficial educational fan project and is not affiliated with or endorsed by Mattel. UNO and related names belong to their respective owners. Card visuals are drawn programmatically with Tkinter Canvas; the project does not bundle official artwork.
