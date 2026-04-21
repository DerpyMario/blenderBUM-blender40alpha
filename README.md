# BUM/LZS Importer

A Unity asset importer for models, animations, and textures from Honey Parade/Marvelous games.
Supports `.bum` model/animation files and `.lzs`/`.lza` compressed/encrypted archives.

> The original Blender Python addon source is preserved in `__init__.py`, `bum.py`, and `lzs.py`.

---

## Supported File Formats

| Extension | Description |
|-----------|-------------|
| `.bum` | Model and animation container (versions 1 and 2) |
| `.lzs` | Compressed archive (LZSS0 or LZ4) containing `.bum` files and textures |
| `.lza` | AES-CBC encrypted LZS archive |
| `.png` / `.dds` | Texture files auto-loaded from the same folder as a `.bum` file |

## Tested Games

- Senran Kagura: New Link
- To LOVE Ru Darkness: Gravure Chances
- Dolphin Wave
- Story of Seasons: A Wonderful Life

---

## Unity Installation

**Requirements:** Unity 2021.3 or newer.

### Option A — Package Manager (recommended)
1. Open **Window > Package Manager**
2. Click the **+** button → **Add package from disk…**
3. Navigate to this repository folder and select `package.json`

### Option B — Manual copy
Copy the entire repository folder into your project's `Assets/` directory.
Unity will automatically detect `Editor/BumImporter.asmdef` and compile the importers.

---

## Usage

Once installed, Unity automatically imports any `.bum`, `.lzs`, or `.lza` file placed inside `Assets/`.

### BUM files
- Place the `.bum` file and its accompanying texture files (`.png`, `.dds`) in the **same folder** inside `Assets/`.
- Unity creates a **Prefab** containing:
  - Bone hierarchy under an `Armature` child object
  - `SkinnedMeshRenderer` (or `MeshRenderer`) for each mesh
  - `Material` sub-assets with textures assigned
  - `AnimationClip` sub-assets for each animation

### LZS / LZA archives
- Place the `.lzs` or `.lza` file anywhere inside `Assets/`.
- Unity extracts the archive and imports all `.bum` models and textures found within.
- Textures are added as sub-assets of the archive asset.

---

## Coordinate System

| Data | Conversion |
|------|-----------|
| Position | `(-x, y, z)` — flip X for left-handed |
| Normal | `(-x, y, z)` |
| Triangle winding | indices `[1]` and `[2]` swapped |
| Quaternion | `(x, -y, -z, w)` |

---

## Project Structure

```
Editor/
  BumImporter.cs        ScriptedImporter for .bum files
  LzsImporter.cs        ScriptedImporter for .lzs and .lza files
  BumModelBuilder.cs    Builds Unity Mesh/Material/SkinnedMeshRenderer/AnimationClip assets
  BumBinaryReader.cs    Little-endian binary reader with IEEE 754 half-float decoding
  BumImporter.asmdef    Editor-only assembly definition
  Formats/
    BumFile.cs          BUM format data structures and parser (v1 and v2)
    LzsFile.cs          LZS/LZA archive parser
    Compression.cs      LZSS0 and LZ4 decompression
    Encryption.cs       AES-CBC decryption for .lza files
package.json            Unity package manifest
```

---

## Credits

- Format research: XenTaX (RIP), UnityPy Server, SoS/RF Modding Server.
- Original Blender Python addon by Al-Hydra.
- Uses Python [pyaes](https://github.com/ricmoo/pyaes) and [PyBinaryReader](https://github.com/mosamadeeb/PyBinaryReader/) in the Blender version.
