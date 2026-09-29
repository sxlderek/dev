---
name: pwgen
description: "Generate a 17-character password starting and ending with lowercase, containing upper+lower+digits+2 underscores at random positions."
version: 1.0.0
author: Hermes
license: MIT
platforms: [linux, macos, windows]
---

# pwgen

Generate a secure password matching these constraints when user types `pwgen`:

## Password Requirements

| Property | Value |
|---|---|
| **Length** | 17 characters |
| **First char** | lowercase a–z |
| **Last char** | lowercase a–z |
| **Must contain** | uppercase (A–Z), lowercase (a–z), digits (0–9) |
| **Must contain** | exactly 2 underscores `_` at random positions (not first/last) |
| **Forbidden** | any special characters other than `_` |

## Algorithm

1. Pick a random lowercase letter for position 0
2. Pick a random lowercase letter for position 16
3. Pick 2 distinct random positions in range [1, 15] for the underscores
4. Fill remaining 13 positions ensuring at least 1 uppercase and 1 digit among them, rest random lowercase
5. Shuffle the 13 middle characters to distribute the uppercase/digit randomly
6. Assemble and output the password

## Usage

Generate a password:
```
pwgen
```

Output should be the password only (no extra text), e.g.:
```
aB7k_d2Lx_m9qRz
```
