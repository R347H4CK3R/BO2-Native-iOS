# PS3 metadata prefix: experimental profile

The previous PC-oriented asset-name table must not be assumed to label the PS3 stream correctly. This repository preserves raw type IDs. The prefix reader accepts only the observed first-record type 52 and rejects other types; this is not a claim that the entire PS3 enum is known.

The supported payload has a three-word name/count/entry-pointer header, an inline UTF-8 name, a fixed-size table of key hash / namespace hash / value pointer triplets, and inline value strings. Previously consumed strings can be referenced by a VIRTUAL-block address.

The layout was compared with the KeyValuePairs and KeyValuePair definitions in the local OpenAssetTools T6 reference (`src/Common/Game/T6/T6_Assets.h`) and its loading directives (`src/ZoneCode/Game/T6/XAssets/KeyValuePairs.txt`). Those definitions are PC-oriented reference evidence, not an authoritative full PS3 schema. The Python reader is independently written and uses no copied C++ implementation.

## Address interpretation

- The initial XFile header consumes 40 file bytes and the XAssetList header consumes 24 TEMP bytes.
- In this limited profile, the pre-asset string and asset tables occupy the VIRTUAL block, so the initial VIRTUAL cursor is the asset-data file offset minus 64.
- Asset headers consume TEMP bytes, not VIRTUAL bytes.
- Alignment changes the allocated VIRTUAL offset; it does not automatically skip bytes in the serialized asset stream.
- A VIRTUAL reference has block bits 5 and a low-bit offset encoded plus one. Only aliases to values actually read with a compatible type can resolve. Shader asset aliases refer to their owning pass pointer slots; technique, declaration and literal aliases refer to allocations.

## Evidence and limits

The first-metadata reader consumes the supplied decoded Tranzit file's initial metadata, including two references back to its inline zone name. The extended prefix reader continues across the layouts described below.

Synthetic tests cover aliases, truncation, unexpected types, non-inline asset references and declared VIRTUAL capacity. Private input and extracted metadata are not test fixtures and are not committed.

There is no engine-execution comparison, general block relocation loader, verified PS3 asset enum, world geometry, collision, or runtime here. All output explicitly keeps complete conversion, geometry verification, and engine-semantics verification false.

## Additional prefix layouts

The extended prefix reader follows known inline records in table order and preserves shared string aliases between them. It currently recognizes:

- Raw type 49: a name and three count/pointer pairs, followed by three arrays of big-endian uint32 values. The observed names identify texture lists. The semantic meaning of the three array categories is not yet established, so they remain numbered arrays in output.
- Raw type 57: a name, vertex-capacity value and four runtime pointer fields. This is a descriptor only; buffer allocation sizes and pointer targets are not resolved.
- Raw type 44: a name, column and row counts, string/hash cell pairs, and a uint16 lookup permutation. The PC StringTable layout is consistent with the observed serialized payload. Cross-asset aliases and all inline strings resolved in the inspected file; lookup indices form a complete permutation of the cells.

## Techniques and model dependencies

Raw type 9 uses a 136-byte TEMP header containing 32 technique pointers. Observed techniques use an 8-byte header followed by 40-byte pass records. Pass children load in vertex shader, declaration, pixel shader, arguments order; the technique name follows. Unknown pass flags are preserved without interpretation. The PS3 slot count and argument categories have supporting [technique asset research](https://codresearch.dev/index.php/Technique_Set_Asset), but public platform layouts must still be checked against the input.

Cached pixel programs use the observed compressed or uncompressed size formula. The observed split variant (last descriptor byte 0x80) stores a program of 16*n+16 bytes followed by a 16-byte cached descriptor. Only that descriptor advances VIRTUAL; physical block placement remains unverified. Vertex program lengths use the low descriptor halfword times four. See the [pixel](https://codresearch.dev/index.php/Pixel_Shader_Asset) and [vertex](https://codresearch.dev/index.php/Vertex_Shader_Asset) structure references. The formulas are constrained to observed pointer arrangements rather than assumed to cover every shader. All bytes remain PS3 programs, with Metal translation explicitly unavailable.

Raw type 5 support is limited to the observed 244-byte zero-filled dependency header with a name pointer. A comma-prefixed name identifies the requested dependency; populated models are rejected rather than treated as converted meshes. The general [BO2 model reference](https://codresearch.dev/index.php/XModel_Asset_(BO2)) is supporting research, not proof of the PS3 populated model layout.

On the supplied decoded Tranzit payload, the reader consumes 487 declared records: 455 model dependencies, 26 technique sets and the six earlier metadata records. It preserves 298 unique populated shader programs (deduplicated by kind and name), including three split payloads. It stops at raw type 46 at byte 689506. Later shared aliases resolve across this prefix, corroborating serialization boundaries and VIRTUAL alignment. This does not establish rendering or gameplay correctness. Reports containing extracted names and bytes stay private.
