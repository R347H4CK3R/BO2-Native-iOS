# Native BO2 implementation plan

The requested result is a native Swift/Metal and Quake-derived iOS game with all required retail content converted locally and embedded in a privately assembled IPA. It must work without the source dump after installation. This document does not establish that the result is feasible or implemented.

## Constraints

- Public GitHub contains source, documentation, and synthetic tests only.
- Source dumps, keys, decoded assets, converted GameData, and final content-bearing IPAs stay outside the repository and GitHub Actions.
- Preserve the source dump. Conversion must be non-destructive.
- Container decoding, asset indexing, synthetic rendering, and successful compilation are separate from gameplay validation.
- No release artifact until every required subsystem and real-content acceptance check has passed.

## First prerequisite: establish the actual conversion boundary

1. Bring the existing deterministic T6 asset-table inspector and its synthetic regression tests into this repository.
2. Add a read-only dump inventory with bounded hashing and explicit unsupported conversion status. Test source preservation, malformed inputs, output boundaries, and exclusive output creation.
3. Run the inventory on the supplied dump and independently re-index the existing decoded Tranzit file. Keep detailed reports local.
4. Run the source-only tests on GitHub macOS and record available Xcode and Simulator versions. These checks do not run BO2 gameplay.

## Unresolved implementation work

1. Resolve PS3 nested asset layouts and block-relative pointers deterministically, including GfxWorld, collision, material/image bindings, models and animation. Compare coordinates and visual results against the real game. Asset-table records alone cannot supply this.
2. Specify and implement versioned native GameData serialization with complete dependency closure, provenance, integrity checks, and memory budgets.
3. Select a license-compatible Quake-derived runtime basis and implement the BO2-specific rendering, physics, animation, audio, entity, weapon, scripting and AI systems. No such integrated runtime is present here.
4. Implement campaign, Zombies and multiplayer semantics, UI/HUD, and simultaneous touch input. Define networking scope before claiming multiplayer completeness.
5. Compile source-only device and simulator binaries in GitHub Actions. Assemble converted content with the device binary locally before signing. Run real-content tests locally/on the physical iPhone; GitHub's synthetic tests cannot validate private assets it does not have.
6. Validate every required map/mode, scripted interactions, collision, progression, save/lifecycle behavior, audio, sustained performance, and cold launch after removing access to the original dump.

An empty app, scanner, procedural arena, or partial map viewer is not an acceptable replacement for the requested game.
