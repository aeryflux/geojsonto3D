# GeoJSON to 3D Globe

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)

Convert GeoJSON geographic data into interactive 3D globe models using Blender.

## Table of Contents

- [Usage](#usage)
- [Features](#features)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Output](#output)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Usage

### Quick Start

```bash
# Run the application
python run.py
```

On first launch:
1. Enter Blender path when prompted (e.g., `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`)
2. Choose a quality preset (1-4)
3. Wait for generation to complete
4. Find your 3D globe in `res/atlas_ico_subdiv_X.glb`

### Quality Presets

```bash
# Fast test (~30 seconds)
python run.py --preset low

# Balanced quality (~1-2 minutes)
python run.py --preset medium

# High quality (~3-5 minutes)
python run.py --preset high

# Maximum quality (~10-20 minutes)
python run.py --preset ultra
```

### Advanced Options

```bash
# Run with Blender GUI visible
python run.py --gui

# Reconfigure all settings
python run.py --configure

# Specify custom Blender path
python run.py --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"

# Show help
python run.py --help
```

### Preset Details

| Preset | ICO_SUBDIV | Faces | Time | Use Case |
|--------|------------|-------|------|----------|
| low    | 3          | 642   | ~30s | Quick testing |
| medium | 4          | 2,562 | ~1-2min | Development |
| high   | 5          | 10,242| ~3-5min | Production |
| ultra  | 6          | 40,962| ~10-20min | Maximum detail |

### Custom Configuration

When choosing "custom" during interactive setup, you can configure:

- **ICO_SUBDIV** (3-7): Globe subdivision level - higher = more detail, slower generation
- **Extrusion** (0.0-0.1): Country height above surface
- **Borders**: Enable/disable 3D country borders
- **Cities**: Enable/disable city markers (significantly slower)

## Features

- 🌍 Spherical projection of GeoJSON polygons onto 3D globe
- 📊 Bidirectional radial extrusion (countries rise above and below surface)
- 🎨 Automatic 3D border generation with anti-z-fighting
- 🎯 Support for complex MultiPolygon geometries
- 📦 GLB export for web/game engines
- ⚙️ Interactive CLI with quality presets
- 💾 Automatic caching of Blender path and configuration

## Installation

1. **Install Blender** (version 2.80+)
   - Download from [blender.org](https://www.blender.org/download/)

2. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/geojsonto3D.git
   cd geojsonto3D
   ```

   ℹ️ **GeoJSON data is included** - Natural Earth data files are already in `data/` directory (public domain).

3. **Run the application**
   ```bash
   python run.py
   ```

## Project Structure

```
geojsonto3D/
├── run.py                              # Main launcher (run this)
├── README.md                           # This file
│
├── src/                                # Source code
│   ├── blender_runner.py              # CLI with interactive configuration
│   └── run.py                         # Blender script (globe generation)
│
├── data/                               # Input GeoJSON data
│   ├── ne_50m_admin_0_countries.geojson
│   └── ne_50m_populated_places.json
│
└── res/                                # Generated 3D models (output)
    └── atlas_ico_subdiv_*.glb         # Auto-created
```

## Configuration

### Cache Files

The tool uses two cache files in the project root:
- `.blender_cache.json` - Stores Blender executable path
- `.config_cache.json` - Stores generation parameters

Delete these files to reset configuration.

### Technical Parameters

- `ICO_SUBDIV`: Icosphere subdivision level (affects quality and performance)
- `EXTRUDE_ABOVE`: Outward extrusion depth (country height)
- `EXTRUDE_BELOW`: Inward extrusion depth
- `BORDER_WIDTH`: Border ribbon width
- `BORDER_HEIGHT`: Border ribbon height
- `ENABLE_BORDERS`: Toggle country borders
- `ENABLE_CITIES`: Toggle city markers

## Output

Generated GLB files are saved to `res/` directory:
- `atlas_ico_subdiv_3.glb` - Low quality
- `atlas_ico_subdiv_4.glb` - Medium quality
- `atlas_ico_subdiv_5.glb` - High quality
- `atlas_ico_subdiv_6.glb` - Ultra quality

### Viewing Results

**Online viewers:**
- [glTF Viewer](https://gltf-viewer.donmccurdy.com/)
- [Babylon.js Sandbox](https://sandbox.babylonjs.com/)
- [Three.js Editor](https://threejs.org/editor/)

**Desktop software:**
- Blender: File → Import → glTF 2.0 (.glb)
- Windows 3D Viewer (Windows 10/11)
- Any 3D software supporting GLB/glTF

**Web frameworks:**
- Three.js, Babylon.js, A-Frame, React Three Fiber

**Game engines:**
- Unity, Unreal Engine, Godot

## Troubleshooting

### Blender not found
```bash
python run.py --configure
```
Then enter the correct path to `blender.exe`

### Script failed
Run in GUI mode to see detailed errors:
```bash
python run.py --gui
```

### Check cache
View current configuration:
```bash
cat .blender_cache.json
cat .config_cache.json
```

### Reset everything
```bash
rm .blender_cache.json .config_cache.json
python run.py --configure
```

### Out of memory
Use a lower quality preset:
```bash
python run.py --preset low
```

## How It Works

1. **Load GeoJSON** - Parse country boundaries from Natural Earth data
2. **Create Icosphere** - Generate base globe with configurable subdivision
3. **Project Countries** - Map GeoJSON polygons onto sphere surface using point-in-polygon
4. **Extrude** - Create 3D relief by bidirectional radial extrusion
5. **Generate Borders** - Create 3D border ribbons along country boundaries
6. **Export GLB** - Save final model in glTF binary format

## Testing

The project includes comprehensive unit and integration tests.

### Run Tests

```bash
# Run all tests
python run_tests.py

# Run specific test file
python -m unittest tests.test_blender_runner
python -m unittest tests.test_integration

# Run with pytest (if installed)
pytest tests/ -v
```

### Test Coverage

The test suite covers:
- ✅ Cache operations (load/save)
- ✅ Blender path verification
- ✅ Configuration presets
- ✅ Script argument building
- ✅ Project structure validation
- ✅ README documentation checks
- ✅ Integration workflows

**35 tests** covering critical functionality with **100% pass rate**.

### Continuous Integration

GitHub Actions automatically runs tests on:
- Multiple OS: Ubuntu, Windows, macOS
- Multiple Python versions: 3.8, 3.9, 3.10, 3.11
- Every push to `master` branch
- Every pull request

## Credits

- **Geographic data**: [Natural Earth](https://www.naturalearthdata.com/)
  - Admin 0 - Countries (1:50m)
  - Populated Places (1:50m)
  - License: Public Domain
- **3D engine**: [Blender](https://www.blender.org/)
- **Export format**: [glTF 2.0](https://www.khronos.org/gltf/)

## Data Attribution

This project includes geographic data from [Natural Earth](https://www.naturalearthdata.com/), a public domain map dataset available at 1:10m, 1:50m, and 1:110m scales.

Natural Earth is made available under **Public Domain** terms. No permission is needed to use Natural Earth. Crediting the authors is unnecessary.

## License

**Code**: This project code is provided as-is for educational and creative use.

**Data**: Geographic data from Natural Earth is in the **Public Domain**.
