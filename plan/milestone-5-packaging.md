# M5 — Desktop Packaging

Last milestone. Per Nitin's chat:
> "Whatever will work. That's too far down the line — let's get it working,
>  let's demo it."

So: do not start this until M3 is solid. Outline the options here so the
choice is informed when we get to it.

## Goal

A user double-clicks an installer. The app starts. They drag in their
Claude / ChatGPT / Gemini exports. They use it. No Python install. No
docker. No psql.

## Three packaging options

### Option A — PyInstaller + pywebview (simplest)

- `pip install pywebview pyinstaller`
- Wrap `convaix serve` startup with `pywebview.create_window("convaix",
  "http://127.0.0.1:0")` after picking a free port.
- `pyinstaller --onefile --windowed convaix_desktop.py`
- Bundles everything Python: FastAPI app, embedded SQLite, sentence-transformers
  model.
- Pros: pure-Python team, fast to build, no Rust toolchain.
- Cons: large binaries (200-500 MB with model weights), slow startup
  (cold-import cost), platform code-signing is annoying.

### Option B — Tauri + Python sidecar

- Tauri (Rust) provides the native window, the menu bar, the auto-updater,
  and the file-drop API.
- A Python sidecar binary (built with PyInstaller) runs the FastAPI server
  on localhost. Tauri webview points at it.
- Pros: small Rust shell, native feel, easier code-signing pipeline.
- Cons: Tauri build chain (Rust + Node) is more moving parts. Bidirectional
  IPC between Tauri and the Python sidecar takes work.

### Option C — Electron + Python sidecar

- Same shape as B but Electron instead of Tauri.
- Pros: more familiar; many examples; node ecosystem for UI.
- Cons: Electron binaries are huge; we don't really need Node.

### Recommendation

Default plan: **A first** (PyInstaller + pywebview) for the demo build,
then graduate to **B** (Tauri sidecar) for the public release once we know
the product is right. This matches the "demo first, package later" rule
and avoids burning weeks on Tauri before we know we're shipping.

## Bundled dependencies

| Component | Strategy |
| --- | --- |
| Python interpreter | Bundled by PyInstaller / Tauri sidecar |
| SQLite + sqlite-vec | Bundled (sqlite-vec ships pre-built wheels) |
| Postgres | **Not bundled** in M5 desktop build. Pg version stays for self-host server users only. |
| Embedding model | nomic-embed-text-v1.5 weights (~270 MB f16). Either ship in installer or download on first run with progress bar. Lean toward "download on first run" for installer size. |
| Ollama | **Not bundled**. App detects and uses it if present; otherwise falls back to API key (OpenAI / Anthropic) or disables RAG. |

## Tasks (when we get here)

### 5.1 — `convaix-desktop` entry point
Single file that starts the FastAPI app on a free port and opens
pywebview window.

### 5.2 — File-drop integration
pywebview supports JS bridge. Add a drop zone in the HTMX UI that POSTs to
`/htmx/import`. Resolves the M3 "stretch" item.

### 5.3 — First-run wizard
- Pick DB location (default: `~/Library/Application Support/convaix/`)
- Download embedding model with progress bar
- Detect Ollama; offer install instructions if not found

### 5.4 — Code signing + notarization
- macOS: Apple Developer ID, `codesign` + `xcrun notarytool`
- Windows: EV cert ($$), `signtool`
- Linux: AppImage or deb / rpm — sign optional

### 5.5 — Auto-update
- Use `pyupdater` with PyInstaller, or `tauri-update` with Tauri
- Tie to GitHub Releases as the update channel

### 5.6 — Telemetry (opt-in)
Just version + crash reports. Sentry free tier is fine. Behind an opt-in
toggle in settings; default off.

### 5.7 — Pricing / payment hook (per Nitin's chat)
> "Desktop app you can charge 25-30$ starting on day 1."

Out of code scope, but: a license-key check at startup, with a 14-day
trial. License keys issued by Gumroad / Lemon Squeezy. Don't gold-plate;
a static key + signature check is enough for v1.

## Definition of done

- A `.dmg` and a `.exe` (or one Tauri bundle) on the GitHub Releases page.
- Double-click → app window → import → search → answer.
- Update notice when a new version is published.

## Risks / mitigations

- **Embedding model size.** Two paths: ship-in-installer (fat installer,
  no first-run network) or download-on-first-run (skinny installer, needs
  network). Pick the latter; show a nice progress UI.
- **Notarization gates on macOS.** Allow several days for Apple's first
  notarization to clear. Plan a builder agent on a Mac for this.
- **License piracy.** Don't bother with a heavy DRM layer for v1. The
  audience cares about the product, not bypassing payment. Watch and
  iterate.
