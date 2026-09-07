# QuickLaunch AI 🚀

A blazing-fast, floating **Spotlight / Raycast-style** AI launcher for Windows, powered by **PySide6**, the **Google GenAI SDK**, the **Antigravity Agent SDK**, and the **Antigravity CLI (`agy`)**.

---

## ✨ Features

- **3 Powerful Operational Modes**:
  1. **⚡ Simple Mode**: High-speed conversational AI with Google Search grounding citations, math evaluation, and sandboxed Python execution.
  2. **🤖 Antigravity Agent Mode**: Multi-turn autonomous agent with live chain-of-thought streaming, tool orchestration, and recursive problem solving.
  3. **🚀 AGY CLI Mode**: Direct integration with the Antigravity CLI (`agy`), streaming thoughts and execution output in real time.
- **Native Windows OS Integration**:
  - Global system-wide hotkey (`Ctrl+Space` by default, customizable in `.env` or settings).
  - Robust 64-bit `WM_HOTKEY` native message filtering with 200ms debounce and automatic conflict cascading.
  - Multi-resolution system tray icon with dark-mode context menu.
  - Windows Taskbar `AppUserModelID` grouping.
- **Raycast-Style Fluid UI**:
  - Borderless frameless dark glass window with subtle borders and shadows.
  - Smooth collapsible height animation (64px search-bar-only up to 560px for rich results).
  - Throttled 30 FPS cursor-based text streaming with single-pass final Markdown rendering to eliminate layout flicker and $O(N^2)$ DOM reconstruction.
  - Horizontal citation chips scroll area with native external link dispatch.
  - Expandable / collapsible reasoning drawer with live word count and status indicator.
  - Persistent query history with `Up` / `Down` arrow recall.
  - Persistent window positioning across monitors with active screen boundary validation.
  - In-app API Key modal (`Ctrl+,`) with masked input and atomic persistence.
- **Security & Sandboxing**:
  - Hardened Python sandbox executing in isolated subprocesses (`python -I -B -`) with sensitive environment variables stripped (`GEMINI_API_KEY`, etc.).
  - Windows process tree termination (`taskkill /F /T`) to prevent orphaned runaway child processes.
  - Safe AST calculator preventing arbitrary code execution, attribute access exploits, and exponential DoS (`2 ** 99999999`).
  - Thread-safe 64-bit Windows clipboard interaction with leak-proof global locks and handle validation.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Space` (Global) | Show / Hide Launcher |
| `Enter` | Submit Prompt / Execute Command |
| `Tab` | Cycle Mode (`⚡ Simple` ↔ `🤖 Agent` ↔ `🚀 CLI`) |
| `Ctrl+P` | Select Model (`gemini-3.1-flash-lite`, `gemini-2.5-flash`, `gemini-3.5-flash`, etc.) |
| `Up` / `Down` | Navigate Query History |
| `Esc` | Hide Launcher / Abort Active Query |
| `Ctrl+C` | Smart Copy (Selected text, or full AI response if none selected) |
| `Ctrl+L` | Clear Input and Results |
| `Ctrl+,` | Open Settings & API Key Configuration Dialog |
| `Double Click Status Bar` | Re-center Window on Current Monitor |

---

## 🚀 Quick Start

### Prerequisites
- Windows 10/11 64-bit
- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (Astral Python project and package manager)

### Installation & Run

1. Clone the repository:
   ```powershell
   git clone https://github.com/hammedrz/quicklaunch-ai.git
   cd quicklaunch-ai
   ```

2. Copy the sample environment file:
   ```powershell
   Copy-Item .env.example .env
   ```
   *(You can add your Gemini API key in `.env` or later directly inside the app using `Ctrl+,`)*

3. Run the application via `uv`:
   ```powershell
   uv run python main.py
   ```

4. Press `Ctrl+Space` anywhere in Windows to summon QuickLaunch AI!

---

## ⚙️ Configuration (`.env`)

QuickLaunch AI can be configured via `.env` or through the in-app settings dialog (`Ctrl+,`):

```env
# Gemini API Key (get from https://aistudio.google.com)
GEMINI_API_KEY=your_gemini_api_key_here

# Default Mode: "simple", "agent", or "cli"
DEFAULT_MODE=simple

# Models
SIMPLE_MODEL=gemini-3.1-flash-lite
AGENT_MODEL=gemini-3.1-flash-lite
CLI_MODEL=

# Global Hotkey (e.g. "ctrl+space", "alt+space", "win+space")
LAUNCHER_HOTKEY=ctrl+space

# Enable/disable Google Search grounding
SEARCH_ENABLED=false

# Code Sandbox execution timeout in seconds
SANDBOX_TIMEOUT=5.0
```

---

## 🧪 Running Tests

The test suite contains 86 comprehensive unit and integration tests covering all modules, services, widgets, and security boundaries:

```powershell
uv run pytest
```

---

## 📁 Project Structure

```
quicklaunch-ai/
├── src/
│   ├── ai/               # Simple, Agent, and CLI services, sandbox, tools
│   ├── ui/               # Frameless launcher window, Markdown view, dialogs, styles
│   ├── config.py         # App configuration and environment loading
│   ├── hotkey.py         # Win32 global hotkey registration & Qt filter
│   ├── state_manager.py  # Persistent window coordinates & query history
│   └── worker.py         # Background QThread for async stream processing
├── tests/                # 86 automated test cases
├── docs/                 # Architectural specifications
├── main.py               # Main application entry point
├── pyproject.toml        # Project metadata and dependencies
└── .env.example          # Template configuration
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
