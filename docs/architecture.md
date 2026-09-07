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

### 7. Project Directory Structure

```
quicklaunch-ai/
├── src/
│   ├── __init__.py
│   ├── config.py              # Application settings, mode preferences, API keys, hotkeys
│   ├── hotkey.py              # Windows Win32 RegisterHotKey & native Qt event filter
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── simple_service.py  # Mode 1: Fast GenAI stream + Search + Sandboxed Code Exec
│   │   ├── agent_service.py   # Mode 2: Google Antigravity Agent + full SDK capabilities
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
│   │   ├── tray.py            # Windows System Tray icon & quick toggle menu
│   │   └── styles.py          # Raycast-inspired dark theme QSS & acrylic effects
│   └── worker.py              # Background QThread handling both Simple & Agent execution
├── docs/
│   └── architecture.md        # This architectural specification
├── tests/
│   ├── __init__.py
│   ├── test_config.py         # Unit tests for settings and mode selection
│   ├── test_sandbox.py        # Unit tests for sandboxed code execution
│   └── test_tools.py          # Unit tests for local system tools
├── main.py                    # Application entry point
├── pyproject.toml
└── .env.example
```
