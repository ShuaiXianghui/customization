# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HyperWorks 2026 fork truck structural part automated modeling tool — targets chassis, mast, and overhead guard assemblies. Provides both GUI and CLI interfaces that drive HyperMesh through its Tcl API. Also see `AGENTS.md` for supplementary notes.

## Running the Tool

| Mode | Command | Notes |
|------|---------|-------|
| GUI (external) | `python main.py` | Launches tkinter GUI, connects via COM/hwx |
| GUI (HM console) | `exec(open(r"D:/Working/OnGoing/customization/startup.py", encoding="utf-8").read())` then `panel()` | Loads quick functions + optional mini panel |
| Batch CLI | `python main.py --batch --input <folder> --output <out.fem>` | Optional: `--shell-size 5.0 --solid-size 8.0` |
| Quick connect | `python launch_gui.py` | Attempts COM/hwx/`__main__.hm` connection then opens GUI |

## Critical Constraint

**Must run inside HyperMesh 2026's embedded Python console for real API access.** External Python enters simulation mode — it logs calls but doesn't operate HyperMesh. The detection chain in `utils/hw_api.py._detect_hm()` tries: `__main__.hm` → `hwx` package → fail (simulation). There is no fallback for HM versions other than 2026 — the `Model.evaltclstring()` API is HM2026-specific.

## 6-Step Modeling Pipeline

```
① Geometry Import → ② Classify (thin-wall vs solid) → ③ Midsurface Extract → ④ Property Assign → ⑤ Meshing → ⑥ Connectors
```

## Architecture: Two Parallel Code Paths

The project has **two implementations** of the same pipeline that serve different use cases:

### 1. `modules/` — Class-based (used by `main.py` GUI and batch mode)

Each module is a stateful class with `run()` returning a typed `@dataclass` result:
- `GeometryImporter` — batch Parasolid import
- `GeometryClassifier` — volume/surface-area ratio + bounding-box ratio dual-strategy thin/solid classification
- `MidsurfaceExtractor` — mid-surface extraction for thin-wall parts
- `PropertyAssigner` — thickness rounding to standard plate values, material matching by part name
- `MeshingEngine` — shell mesh (thin parts) and solid mesh (solid parts)
- `ConnectorEngine` — auto-detect seam welds, bolts, spot welds between part pairs

### 2. `tools/` — Standalone scripts (run individually in HM console)

Each script reads its own config at the top (marked `★★★`), calls `hm.Model().evaltclstring()` directly:
- `import_parasolid.py`, `extract_midsurface.py`, `assign_property.py`, `auto_mesh.py`, `create_connectors.py`
- `run_all.py` — chains the above 4 (assumes geometry already imported)
- `clear_all.py` — deletes all components
- `load_all.py` — imports API functions into console namespace as quick commands (`midsurface()`, `assign_prop()`, `mesh()`, etc.)
- `panel.py` — standalone tkinter mini-panel for HM console use (non-blocking via threading)

### 3. `startup.py` — HM console entry point

Force-refreshes all project modules (deletes from `sys.modules` first), imports API layer, and defines shorthand functions (`midsurface()`, `assign()`, `mesh()`, `weld()`, `cls()`, `panel()`). Hardcodes a material dict and standard thickness list. This is the recommended way to reload after code changes.

## Key Files

| File | Role |
|------|------|
| `utils/hw_api.py` | **All HyperMesh interaction**. Auto-detects HM availability, wraps every Tcl command as Python functions. Only file that calls `hm.Model().evaltclstring()`. |
| `config/settings.py` | Global defaults: standard thicknesses [3-30mm], mesh quality thresholds, connector parameters, classify/midsurface configs |
| `config/material_db.json` | 8 fork truck steels (Q235 through QT450-10) with E, nu, rho, yield, uts |
| `utils/logger.py` | Singleton logger with optional GUI callback (redirects to tkinter Text widget) |
| `utils/validators.py` | File/format validation (Parasolid extension check, thickness/element-size ranges, material code patterns) |
| `gui/main_window.py` | Full tkinter app: left sidebar with 6-step navigation + one-click pipeline, right panel area, bottom log/progress |
| `gui/widgets.py` | Reusable tkinter components: `FileListBox`, `LogPanel`, `ProgressFrame`, labeled entry/combo/folder selectors |
| `gui/panels/` | One panel per pipeline step, each wraps its corresponding `modules/` class |

## Data Flow Between Steps

Each step's `@dataclass` result feeds the next:
- `ImportResult` → file list and component IDs
- `ClassifyResult` → `thin_parts: list[PartInfo]` + `solid_parts: list[PartInfo]` (each has `comp_id`, `name`, `volume`, `surface_area`, `bbox_dims`)
- `MidsurfaceResult` → `thickness_map: dict[comp_id, float]`
- `PropertyResult` → `records: list[PropertyRecord]` (standardized thickness + material per part)
- `MeshResult` → per-part mesh records
- `ConnectorResult` → detected and created connector candidates

## Code Conventions

- 2-space indentation throughout
- camelCase variables, verb-prefixed function names, Chinese comments
- Module results use `@dataclass` with `success: bool` + `message: str` + typed payload fields
- All HM API calls go through `utils/hw_api.py` — classes never call `hm` directly
- Config is loaded at module level, not passed through constructors
- `session` parameter is threaded through all module classes (defaults to `get_session()`)

## Validation

```bash
python -m py_compile <file>          # Single-file syntax check
python -c "from modules.<name> import <Class>; print('OK')"  # Module import test
```

No test framework is configured; `tests/__init__.py` exists but is empty.

## Dependencies

Zero external dependencies. Uses only Python standard library: `tkinter`, `json`, `argparse`, `logging`, `threading`, `dataclasses`, `enum`, `os`, `sys`.
