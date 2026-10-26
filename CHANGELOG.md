# Changelog: halo.spaces for Windows

Changes in this fork compared with [halo.spaces](https://github.com/sruf79/halo-spaces). Upstream's
own release notes are on its [Releases](https://github.com/sruf79/halo-spaces/releases) page.

## Unreleased: merged halo.spaces 3.6.0 and 3.7.0, 2026-10-26

**Tested with Thunderbird 158 on Windows 11 at 125 % scaling: 246/246 checks pass in light and dark**

### ✨ New features
- **Merged upstream halo.spaces 3.6.0 and 3.7.0** (Undo Send, Send Later, Remind Me, Quick Reply, weather in the Today pane …)
- **Temperature next to the weather symbol in the Today pane**
- **Double-clicking a message opens it in its own window** (the tab bar is hidden; Esc or Ctrl+W close tabs)

### 🐛 Fixes
- **Buttons in the toolbar row react to clicks again** (Windows had treated them as part of the title bar)
- **Tests: line widths compared correctly at 125 % scaling**

## Merged halo.spaces 3.5.1, 2026-10-24

### ✨ New features
- **Merged upstream halo.spaces 3.5.1**
- **Alt menu bar as a full-width strip at the top of the window**
- **Option: all unified folders (Drafts, Trash, Spam …) in Favourites**

## First Windows version (based on halo.spaces 3.3.0), 2026-10-24

**Tested with Thunderbird 158 on Windows 11 at 125 % scaling: 197/197 checks pass in light and dark**

### ✨ New features
- **One-click install, update and uninstall (`halo-spaces.cmd`)**
- **Windows build without zsh (`build.py`)**
- **Segoe UI Variable as the Windows font**
- **≡ menu hidden like on macOS; Alt shows the menu bar**
- **Compose and event windows: menu bar only with Alt**
- **"On This PC" instead of "On My Mac"**
- **Settings → Appearance says "follow Windows"**
- **Updates come from this fork**

### 🐛 Fixes
- **Today pane title and "+" no longer overlap the window buttons**
- **Folder pane buttons in the right order and place**
- **"Add Location or Video Call" no longer cut off**
- **Help window not scrollable at 125 %/150 % scaling**
- **No thin bar on the space arrow at 125 %/150 % scaling**
- **Build no longer depends on the Windows code page**

### Removed
- **Send Feedback and Say Thanks buttons**
- **"Made for macOS" notice on Windows**

### Tests
- **Test suite runs natively on Windows**
- **Light runs are really light; accent colour pinned in the test profile**
- **Checks tolerate display scaling, a Monday week start and a second monitor**
