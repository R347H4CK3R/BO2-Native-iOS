# BO2-Native-iOS

Work in progress. **This repository does not contain a playable BO2 port or a finished IPA.**

The target is a self-contained native iOS game using locally converted BO2 content, with Swift/Metal rendering, a Quake-derived runtime, touch controls, and no PS3 emulator. The complete target and unresolved work are in [the implementation plan](docs/implementation-plan.md).

## Implemented here

- A read-only source inventory with streaming SHA-256 hashes and explicit conversion status.
- A deterministic inspector for the declared big-endian T6 XAssetList in an already decoded XFile. It reads asset record types and serialized pointers; it does **not** resolve nested assets, geometry, or gameplay.
- An experimental reader for a first-asset metadata layout observed in the PS3 Tranzit stream. It resolves inline strings and known virtual-block string aliases, then stops at the next unsupported asset. It is not a general PS3 type map or GameData converter.
- Synthetic parser and source-preservation tests.
- A macOS Actions workflow for these tests and Xcode/Simulator availability checks. This is not a game build or a gameplay test.

## Local commands

Python 3.12 or later, standard library only:

```text
python -m unittest discover -s Tools/tests -v
python Tools/dump_inventory.py /path/to/PS3_GAME --report /private/output/source-inventory.json
python Tools/t6_asset_index.py /private/input/zm_transit.ff.decoded --report /private/output/asset-index.json
python -m Tools.t6_metadata_prefix /private/input/zm_transit.ff.decoded --report /private/output/metadata-prefix.json
```

Do not place source dumps, keys, decoded content, converted GameData, or final content-bearing IPAs in this repository or Actions artifacts. The inventory tool rejects report destinations inside the dump or repository and refuses to overwrite existing reports.

The decoded input for the indexer must be produced separately; this repository currently has no complete PS3 asset converter. Existing local experimental decoder tools are not evidence that maps, textures, collision, models, animation, scripts, or rules are converted.

## Delivery boundary

GitHub may build source-only binaries when the native runtime is implemented. Converted retail content is assembled with the device binary locally, before signing. Full real-content testing must run where those private assets are available, including the physical iPhone. Passing synthetic CI alone must never unlock a finished-game release.
