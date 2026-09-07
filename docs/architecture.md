# QuickLaunch AI (Windows Raycast / Spotlight Style)
## Architecture Design & Technical Specification (Dual-Mode Edition)

### 1. Executive Summary
**QuickLaunch AI** is a keyboard-first desktop companion for Windows engineered with a macOS Spotlight / Raycast aesthetic. Summoned instantly via a global keyboard shortcut (default: `Alt + Space`), it supports **Dual Operating Modes**:

1. **⚡ Quick / Simple Mode (Instant Spotlight)**:
   - Ultra-fast, lightweight streaming responses.
   - Built-in tools: Real-time **Google Search grounding**, **Sandboxed Python Code Execution**, safe math calculation, and clipboard utilities.
   - Optimized for instant queries, quick searches, fact checking, calculations, and code snippets.
2. **🤖 Antigravity Agent Mode (Full Autonomous Agent)**:
   - Full autonomous agent power powered by the **Google Antigravity SDK** (`google.antigravity.Agent`).
   - Capabilities: Multi-step reasoning with live thought streaming (`response.thoughts`), built-in web tools (`SEARCH_WEB`, `READ_URL_CONTENT`), file inspection (`VIEW_FILE`), shell execution (`RUN_COMMAND`), lifecycle tool hooks, subagents, and MCP server connectivity.
   - Optimized for complex tasks, multi-step research, codebase exploration, and deep problem-solving.

Users can toggle seamlessly between modes at any time using `Tab`, `Ctrl + M`, or by clicking the interactive mode pill directly inside the search bar.

---

### 2. High-Level Architecture Diagram

```
                             [ User presses global hotkey: Alt + Space ]
                                                │
                                                ▼
                         ┌─────────────────────────────────────────────┐
                         │   Native Windows Event Filter (Win32 API)   │
                         │   - RegisterHotKey (WM_HOTKEY: 0x0312)      │
                         │   - QAbstractNativeEventFilter              │
                         └──────────────────────┬──────────────────────┘
                                                │
                                                ▼
                         ┌─────────────────────────────────────────────┐
                         │       RaycastLauncherWindow (PySide6)       │
                         │   - Frameless, translucent dark acrylic     │
                         │   - Mode Toggle Pill: [⚡ Quick] ↔ [🤖 Agent]│
                         │   - Hotkey: Tab or Ctrl+M to switch mode    │
                         │   - Input box, thinking drawer, markdown view│
                         └──────────────────────┬──────────────────────┘
                                                │
                         ┌──────────────────────┴──────────────────────┐
                         │                                             │
               (If Simple Mode)                              (If Agent Mode)
                         │                                             │
                         ▼                                             ▼
        ┌──────────────────────────────────┐         ┌──────────────────────────────────┐
        │       Simple Engine Worker       │         │     Antigravity Agent Worker     │
        │   - Direct Google GenAI Stream   │         │   - google.antigravity.Agent     │
        │   - Google Search Grounding      │         │   - Multi-step reasoning loop    │
        │   - Sandboxed Code Execution     │         │   - Thought streaming            │
        │   - Instant math / quick actions │         │   - Built-in & custom SDK tools  │
        └──────────────────────────────────┘         └──────────────────────────────────┘
```

---

### 3. Dual Mode Breakdown

| Feature | ⚡ Simple Mode | 🤖 Antigravity Agent Mode |
| :--- | :--- | :--- |
| **Engine** | Direct `google-genai` SDK | `google.antigravity.Agent` (`LocalAgentConfig`) |
| **Primary Use Case** | Instant answers, search lookups, code snippets, math | Deep multi-step tasks, research, full workflows |
| **Default Tools** | Google Search Grounding, Sandboxed Python Exec, Calc | `SEARCH_WEB`, `READ_URL_CONTENT`, `VIEW_FILE`, `RUN_COMMAND`, custom tools |
| **Thinking / Thoughts** | Standard token streaming | Live collapsible `response.thoughts` streaming |
| **Tool Execution** | Deterministic function calling / Grounding | Autonomous agent loop with SDK pre/post tool hooks |
| **Speed & Latency** | Sub-second first-token response | Multi-turn planning with full agent capabilities |
| **UI Badge** | Cyan/Blue `[⚡ Simple | 🌐 Search]` | Purple/Amber `[🤖 Agent | 🧠 Autonomous]` |

---

### 4. Sandboxed Code Execution & Tools in Simple Mode

Simple Mode incorporates a safe, isolated Python execution environment:
* **`SandboxedCodeExecutor`**:
  * Executes short Python scripts or math expressions in a restricted subprocess with a strict execution timeout (default 5s).
  * Captures `stdout` and `stderr` safely.
  * Blocks network access and destructive OS operations during simple mode execution.
* **Google Search Grounding**:
  * Native Google Gemini Search Grounding extracts live web results with inline URL citations.
* **Quick Tools**:
  * Fast calculator, unit conversions, clipboard manager.

---

### 5. Google Antigravity Agent Mode Architecture

Agent Mode unleashes the full `google-antigravity` framework:
* **Session & Conversation**: Stateful conversation tracking across multiple turns.
* **Built-in Capabilities**:
  * `BuiltinTools.SEARCH_WEB` (Enabled by default)
  * `BuiltinTools.READ_URL_CONTENT` (Web scraper for full article analysis)
  * `BuiltinTools.VIEW_FILE` (Inspect local files)
  * `BuiltinTools.RUN_COMMAND` (Configurable command execution)
* **Lifecycle Hooks**:
  * `@hooks.pre_tool_call_decide`: Broadcasts tool name and arguments to the Qt UI thread to display real-time action chips (`[🌐 Searching Google: "latest AI news"]`).
  * `@hooks.post_tool_call`: Broadcasts tool completion.
* **Thinking Stream**:
  * Subscribes to `response.thoughts` to display the agent's internal chain-of-thought in an expandable drawer above the response.

---

### 6. User Interface & Interactions

* **Visual Design**:
  * Dark acrylic/matte glass styling (`#161618` window, `#2a2a2e` border, 16px corner radius, drop shadow).
* **Interactive Mode Switcher**:
  * Positioned on the right side of the search bar or togglable via `Tab` / `Ctrl + M`.
  * Instantly switches between `[⚡ Simple]` and `[🤖 Agent]` modes with smooth badge transition.
* **Action Footer**:
  * `⏎ Submit` • `Tab Switch Mode` • `Esc Dismiss` • `Ctrl+C Copy` • `Ctrl+L Clear`.
* **Thought Viewer**:
  * Appears in Agent mode, allowing the user to peek into the model's thoughts with a click or via `Ctrl + T`.

---

---

### 7. Windows Startup & Task Manager Integration

QuickLaunch AI provides a native **"Run at Startup"** capability engineered specifically for Windows Task Manager compatibility:

* **Name Resolution in Task Manager**:
  * Instead of registering a direct Python executable in `HKCU\...\Run` (which causes Task Manager to display generic labels like `"Python"` or `"pythonw"`), QuickLaunch AI creates a formatted Windows shortcut (`QuickLaunch AI.lnk`) in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.
  * Task Manager's **Startup apps** section uses the `.lnk` file's name (`QuickLaunch AI`), guaranteeing correct display, icon, and publisher attribution.
* **Development vs. Production Targets**:
  * **Development Mode**: Targets `pythonw.exe` with `"{project_root}/main.py" --autostart`, ensuring no terminal window flashes on system boot.
  * **Production Mode**: When packaged (`sys.frozen`), dynamically targets the compiled binary (`sys.executable`).
  * Explicitly pins `WorkingDirectory` to the project root so `.env` and configuration paths resolve reliably.
* **Two-Way Task Manager Synchronization**:
  * Inspects `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder`.
  * When a user enables or disables QuickLaunch AI inside Task Manager's "Startup apps" tab, Windows records a binary flag (`0x02` = enabled, `0x03` = disabled). The tray menu dynamically checks this key on opening to ensure the UI checkbox always matches Task Manager's state.
* **Silent Boot Mode (`--autostart`)**:
  * When launched with the `--autostart` argument, the application initializes quietly into the system tray, suppressing the welcome balloon notice and keeping the launcher window dismissed until the user presses the global hotkey.

---

### 8. Project Directory Structure

```
quicklaunch-ai/
├── src/
│   ├── __init__.py
│   ├── autostart.py           # Windows Startup Apps & Task Manager synchronization
│   ├── config.py              # Application settings, mode preferences, API keys, hotkeys
│   ├── hotkey.py              # Windows Win32 RegisterHotKey & native Qt event filter
│   ├── logger.py              # Rotating file and console logging configuration
│   ├── state_manager.py       # Persistent window coordinates & query history
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── simple_service.py  # Mode 1: Fast GenAI stream + Search + Sandboxed Code Exec
│   │   ├── agent_service.py   # Mode 2: Google Antigravity Agent + full SDK capabilities
│   │   ├── model_registry.py  # Gemini model discovery & cache management
│   │   ├── sandbox.py         # Sandboxed Python code executor for Mode 1
│   │   ├── hooks.py           # Antigravity SDK lifecycle hooks for Mode 2
│   │   └── tools/             # Shared & custom tools
│   │       ├── __init__.py
│   │       ├── system_tools.py# Calculator, system info, clipboard, app launcher
│   │       └── code_tools.py  # Sandboxed code execution tool
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── launcher_window.py # Main Raycast-style floating window with animations
│   │   ├── search_bar.py      # Input field with interactive Mode Pill & progress spinner
│   │   ├── thought_view.py    # Collapsible agent reasoning ("Thinking...") viewer
│   │   ├── result_view.py     # Markdown renderer with syntax highlighting & citation chips
│   │   ├── status_bar.py      # Contextual keyboard hints (⏎ Submit, Tab Mode, Esc Dismiss)
│   │   ├── tray.py            # Windows System Tray icon, menu, & autostart toggle
│   │   ├── api_key_dialog.py  # Settings modal for Gemini API key configuration
│   │   ├── drag_handle.py     # Frameless window drag region
│   │   └── styles.py          # Raycast-inspired dark theme QSS & acrylic effects
│   └── worker.py              # Background QThread handling both Simple & Agent execution
├── docs/
│   └── architecture.md        # This architectural specification
├── tests/
│   ├── __init__.py
│   ├── test_autostart.py      # Unit tests for Startup apps & Task Manager registry sync
│   ├── test_config.py         # Unit tests for settings and mode selection
│   ├── test_hotkey.py         # Unit tests for hotkey parsing and Win32 registration
│   ├── test_sandbox.py        # Unit tests for sandboxed code execution
│   └── test_tools.py          # Unit tests for local system tools
├── main.py                    # Application entry point with --autostart support
├── pyproject.toml
└── .env.example
```
