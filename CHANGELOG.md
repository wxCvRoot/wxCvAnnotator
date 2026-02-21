# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-21

### Added
- **Internationalization**: Completed 100% translation coverage for 8 additional languages:
  - `ru_RU` Russian (俄語)
  - `fa_IR` Persian / Farsi (波斯語)
  - `ar_SA` Arabic (阿拉伯語) — RTL layout supported
  - `es_ES` Spanish (西班牙語)
  - `de_DE` German (德語)
  - `fr_FR` French (法語)
  - `th_TH` Thai (泰語)
  - `tr_TR` Turkish (土耳其語)
- **i18n Tooling** (`tools/i18n/manage_i18n.py`):
  - New `reset` command: clears fake translations where `msgstr == msgid` (except `en_US`)
  - Progress report now shown before `todo` export
  - `fill` command auto-rebuilds `.mo` files after merging

### Changed
- i18n tools moved to `tools/i18n/` directory for cleaner project layout
- `manage_i18n.py` now handles all workflow steps: `extract → todo → fill → build → reset`

---

## [Unreleased] - 2026-02-20

### Changed
- Default language changed from `zh_TW` to `en` in `settings.default.json`.
- Startup no longer displays a test image; the canvas starts empty until the user opens a file.
- Minimum Python version lowered from 3.10 to **3.8** to match wxCvModule support matrix.
- GitHub Actions CI matrix updated to cover Python 3.8–3.14 across Windows, Linux, macOS,
  mirroring the wxCvModule release matrix.

### Removed
- `_load_test_image()` method and its call in `image_display_panel.py` (was generating a synthetic numpy image on startup).

### Fixed
- `ci.yml`: `exclude`/`include` moved inside `matrix:` (indentation error caused workflow parse failure).
- `ci.yml`: replaced `pip install dist/*.whl` with `pip install --no-index --find-links dist wxcvannotator`
  to fix glob expansion failure on Windows PowerShell.

---

## [0.0.1] - 2026-02-19

### Added
- Initial release of wxCvAnnotator.
- Core annotation tools: Polygon, Rectangle, Rotated Rect, Circle, Point.
- AI-assisted labeling integration with SAM, SAM 2, and EfficientSAM.
- Internationalization support (English, Japanese, Traditional Chinese).
- Theme management (Dark/Light modes).
- Export systems for YOLO, COCO, Pascal VOC, and CSV.
- Comprehensive documentation in `docs/`.

### Changed
- Centralized version management in `wxcvannotator/__init__.py`.
- Refactored project structure to a standard Python package.
- Cleaned up i18n folder structure and metadata.

### Fixed
- Duplicate language entries in the UI menu.
- Relative import issues in the main application package.
- Encoding and path issues in the test suite.
