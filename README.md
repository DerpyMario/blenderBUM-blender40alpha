# blenderBUM

A Blender addon for importing models, animations, and textures from Honey Parade/Marvelous games.

## Supported File Formats

- **`.bum`** - Model and animation container (versions 1 and 2)
- **`.lzs`** - Compressed container (LZSS0 or LZ4 compression)
- **`.lza`** - Encrypted LZS container
- **Textures** - `.png`, `.dds`, `.bc7`, `.astc`, anything blender supports natively.

## Installation

1. Download the latest release or clone this repository
2. In Blender, go to `Edit > Preferences > Add-ons`
3. Click `Install...` and select the addon folder
4. Enable the addon by checking the checkbox next to "Import: BUM/LZS Importer"

## Usage

### Import via Menu
1. Go to `File > Import > LZS Container Importer (.lzs)`
2. Navigate to your file and select it
3. Click `Import`

### Import via Drag & Drop
Simply drag and drop `.bum`, `.lzs`, or `.lza` files directly into the 3D viewport.

### Texture Loading
When importing `.bum` files, the addon automatically scans the same directory for texture files and loads them with matching material names.
When importing `.lzs` or `.lza`, textures found in the archive will be automatically loaded first.

## Tested Games

- Senran Kagura: New Link
- To LOVE Ru Darkness: Gravure Chances
- Dolphin Wave
- Story of Seasons: A Wonderful Life

## Requirements

- Blender 4.5.0 or higher (older versions might be supported but not tested).

## Credits

- Uses modified versions of [pyaes](https://github.com/ricmoo/pyaes) and [PyBinaryReader](https://github.com/mosamadeeb/PyBinaryReader/)
- XenTaX (RIP) bum format info.
- UnityPy Server Members for their research.
- SoS/RF Modding Server for their research.
