# UNO No Mercy v6.0.0

A desktop LAN card game for 2–6 players, with solo bot practice, animated card play, draw stacking, hand swaps, and custom 36-card elimination.

## Choose Your Download

| Filename suffix | Platform | Start the game |
| --- | --- | --- |
| `windows-x64.zip` | 64-bit Windows; intended for Windows 10/11 | Extract everything, then open `UNO-No-Mercy/UNO-No-Mercy.exe`. |
| `macos-x64.zip` | Intel Mac; built on macOS 15 | Extract and open `UNO-No-Mercy.app`. |
| `macos-arm64.zip` | Apple Silicon Mac; built on macOS 14 | Extract and open `UNO-No-Mercy.app`. |
| `linux-x64.tar.gz` | x86-64 Linux; built on Ubuntu 22.04 | Extract and run `./UNO-No-Mercy/UNO-No-Mercy`. |

Native packages bundle Python and Tcl/Tk. Keep the extracted application folder intact. A graphical desktop is required. Older operating systems than the build runners have not been verified.

Each archive has a matching SHA-256 checksum file. `BUILD_CHECK.json` inside the archive records the automated checks performed on that build.

## Included

- LAN rooms with six-digit room codes and protocol version 6.
- Solo practice with up to five bots.
- Double-click and drag-to-play controls, color selection, and UNO shortcuts.
- Draw penalties, color roulette, 7 hand swaps, and 0 hand passing.
- Configurable round-ending thresholds and final rankings.
- Same-window reconnect and host-controlled bot takeover.

## Release Details

- The application interface is in Simplified Chinese; project documentation is in English.
- All players should use the same version. Use trusted local networks; the server has no TLS or public matchmaking.
- The nicknames `admin` and `op` enable author mode. Use other names for standard rules.
- Windows builds are unsigned. macOS builds are not Developer ID signed or notarized, so operating-system security prompts may appear.
- Automated startup checks do not cover manual gameplay, animation quality, or cross-device Wi-Fi behavior.
- A separately labeled `linux-x64-glibc2.39-headless-check` package is a local build requiring glibc 2.39 or newer; its GUI startup was not checked. Use the GitHub-built Linux package for the older Ubuntu 22.04 build baseline.

This is an unofficial educational fan project, unaffiliated with Mattel.
