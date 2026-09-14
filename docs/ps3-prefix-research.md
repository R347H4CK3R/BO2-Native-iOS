# PS3 metadata prefix: experimental profile

The previous PC-oriented asset-name table must not be assumed to label the PS3 stream correctly. This repository preserves raw type IDs. The prefix reader accepts only the observed first-record type 52 and rejects other types; this is not a claim that the entire PS3 enum is known.

The supported payload has a three-word name/count/entry-pointer header, an inline UTF-8 name, a fixed-size table of key hash / namespace hash / value pointer triplets, and inline value strings. Previously consumed strings can be referenced by a VIRTUAL-block address.

The layout was compared with the KeyValuePairs and KeyValuePair definitions in the local OpenAssetTools T6 reference (`src/Common/Game/T6/T6_Assets.h`) and its loading directives (`src/ZoneCode/Game/T6/XAssets/KeyValuePairs.txt`). Those definitions are PC-oriented reference evidence, not an authoritative full PS3 schema. The Python reader is independently written and uses no copied C++ implementation.

## Address interpretation

- The initial XFile header consumes 40 file bytes and the XAssetList header consumes 24 TEMP bytes.
- In this limited profile, the pre-asset string and asset tables occupy the VIRTUAL block, so the initial VIRTUAL cursor is the asset-data file offset minus 64.
- Asset headers consume TEMP bytes, not VIRTUAL bytes.
- Alignment changes the allocated VIRTUAL offset; it does not automatically skip bytes in the serialized asset stream.
- A VIRTUAL reference has block bits 5 and a low-bit offset encoded plus one. Only aliases to strings actually read by this reader can resolve.

## Evidence and limits

The reader consumed the first metadata layout of the supplied decoded Tranzit file, including two references back to its inline zone name. Its next cursor reaches a payload containing a texture-list name, but the structure of that subsequent asset is not implemented or verified.

Synthetic tests cover aliases, truncation, unexpected types, non-inline asset references and declared VIRTUAL capacity. Private input and extracted metadata are not test fixtures and are not committed.

There is no engine-execution comparison, general block relocation loader, verified PS3 asset enum, world geometry, collision, or runtime here. All output explicitly keeps complete conversion, geometry verification, and engine-semantics verification false.
