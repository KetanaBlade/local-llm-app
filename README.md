# Local AI Studio — Universal On-Device Workstation

A 100% private, zero-telemetry, air-gapped local AI studio that combines a responsive conversational web interface with an autonomous **Antigravity Agent Engine**. Capable of generating live neural images (SD 1.5 & SDXL), production-grade Excel spreadsheets (`.xlsx`) with formulas, formatted PDF/Word documents, interactive HTML/JS applications, deep web research with residential IP bot-shielding, and executing Python in a sandboxed runtime—completely on-device.

---

## Architecture Overview

```
                          ┌────────────────────────────────────────────────────────┐
                          │                Client Presentation Tier                │
                          │   React 18 + Tailwind CSS + Lucide Icons + Vite        │
                          │   (Desktop Web Browser / Frameless App / Mobile Wi-Fi) │
                          └───────────────────────────┬────────────────────────────┘
                                                      │ HTTP / SSE Stream
                                                      ▼
                          ┌────────────────────────────────────────────────────────┐
                          │               FastAPI LAN Gateway (:8000)              │
                          │   - Privacy & Subnet Guard (Localhost & LAN only)      │
                          │   - Server-Sent Events (SSE) Streaming Engine          │
                          │   - Lifecycle Manager (Sleep Mode & Shutdown)          │
                          └──────┬────────────────────┬────────────────────┬───────┘
                                 │                    │                    │
              ┌──────────────────┴──────────┐         │                    └─────────────────┐
              ▼                             ▼         ▼                                      ▼
┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
│     Ollama LLM Engine     │ │   Stable Diffusion.cpp    │ │  SQLite Database Layer    │ │   Agent Tools & Sandbox   │
│   (Port 11434 Daemon)     │ │     (sd-cli / Vulkan)     │ │    (WAL Mode + Secure     │ │  - openpyxl (Excel .xlsx) │
│ - Llama 3.2 / Hermes 3    │ │ - SD 1.5 & SDXL Checkpoints│ │       Obliteration)       │ │  - reportlab / python-docx│
│ - Hardware-Tuned num_ctx  │ │ - Embedded Metadata Parser│ │ - Conversations & Context │ │  - Python Execution Box   │
│ - Zero-VRAM Auto-Eviction │ │ - Dynamic Style Routing   │ │ - Artifact Tracking       │ │  - Deep Shielded Search   │
└───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘
                                                                                                     │
                                                      ┌──────────────────────────────────────────────┴───────────┐
                                                      ▼                                                          ▼
                                      ┌───────────────────────────────┐                          ┌───────────────────────────────┐
                                      │   Jina Cloud Reader Proxy     │                          │    Brave API / DuckDuckGo     │
                                      │   (r.jina.ai - Remote Cluster)│                          │    (Keyword Search Engine)    │
                                      │   - Residential IP Hidden     │                          │    - Query De-Noising         │
                                      │   - Cloudflare/Bot-Shielded   │                          │    - Untrusted XML Boundary   │
                                      └───────────────────────────────┘                          └───────────────────────────────┘
```

---

## Key Capabilities & Features

### 1. Deep Web Search & Residential IP Bot-Shielding
Upgrades local search from shallow truncated snippets into deep article research with full protection against bot-flagging:
* **Zero Residential IP Exposure (Jina Reader Proxy)**: When reading web articles, Local AI Studio never connects directly to target websites from your home IP. Instead, article markdown is fetched via remote Jina Reader cloud proxies (`https://r.jina.ai/<url>`). Target sites only see remote data center clusters—your residential IP address remains 100% hidden, eliminating any risk of Cloudflare, Akamai, or bot blacklisting.
* **Dual Indexing Engines**:
  * **Out-of-the-Box Mode (Default)**: Uses DuckDuckGo search via authentic browser POST submissions with automatic `/l/?uddg=` destination redirect unquoting and Lite fallback. Zero setup, zero API keys required.
  * **Official Brave Search API (Optional)**: Free integration with the official Brave Search API (`api.search.brave.com`, 2,000 free queries/month). Easily configured via the Hardware & Settings modal with one-click key visibility toggle.
* **Odysseus Anti-Injection Boundaries**: Retrieved web contents are quarantined inside `<untrusted_web_source>` tags with explicit agent rules preventing **indirect prompt injection** attacks from untrusted websites.
* **Query De-Noising & Cookie Scrubbing**: Conversational filler (*"can you search online for..."*) is stripped before querying, and cookie banners, newsletter overlays, and paywalls are filtered out before reaching context.
* **Interactive Source Chips `[1]`, `[2]`**: Responses ground facts in numbered source citations, with one-click chips that open original articles in a new tab.
* **Strict Air-Gap Switch**: When "Offline" mode is active, all outgoing web requests are blocked at the engine root.

### 2. Multi-Model Neural Diffusion & SDXL Engine
Directly runs quantized Stable Diffusion checkpoints on your local GPU via Vulkan compute:
* **Safetensors Metadata Inspector**: Inspects embedded `modelspec.title` and tensor headers directly on disk to extract authentic checkpoint names, base architecture (SD 1.5 vs. SDXL), and recommended resolutions (512×512 or 1024×1024).
* **SDXL Support**: Native support for high-resolution SDXL checkpoints (e.g. Pony Diffusion V6 XL) running at native 1024×1024 resolution.
* **Dynamic Style Selector**: The image composer dropdown automatically populates from all installed checkpoints in `models/image/`, letting you select models like CyberRealistic, MeinaMix, DreamShaper, or Pony Diffusion with zero prompt refusal.
* **Direct Image Mode**: Dedicated toggle in the composer that routes prompts directly to local diffusion on your GPU, completely bypassing LLM parsing and moralizing refusals.

### 3. Model Hub & Storage Reclaimer
* **Dual-Tab Hub**: Separate tabs for **Conversational LLMs** and **Image Models** in the Model Hub modal.
* **One-Click Deletion**: Safely delete unused Ollama LLMs or large diffusion checkpoints (`.safetensors`) directly from the UI to reclaim tens of gigabytes of disk space.
* **Progress Tracking**: Real-time progress bars for Ollama pulls and direct HTTP checkpoint downloads with automatic rename handling.

### 4. Antigravity-Grade Orchestrator & Multi-Project Hierarchy
Upgrades local LLMs from rigid form-fillers into an autonomous pair programmer equipped with universal execution primitives:
* **Multi-Project Organization**: Create isolated **Managed Projects** (`workspace/projects/<slug>/`) or link any existing directory or repository on your computer (**Link Local PC Folder**) using the native Windows folder picker.
* **Human-in-the-Loop Tool Permissions**:
  * **Ask on Write/Exec (Default)**: Automatically permits read-only operations (`read_file`, `list_directory`, `search_web`), but pauses to display an interactive approval card with `[ Allow Once ]`, `[ Always Allow Tool ]`, and `[ Deny ]` before running shell commands, executing code, or editing files.
  * **Autonomous (Allow All)**: Runs all tools without interruption.
  * **Plan Only (Read Only)**: Explores codebases and plans changes without modifying files or executing scripts.
  * **Configurable Matrix**: Fully customizable per-tool permission matrix in Studio Settings (`⚙️`).
* **In-Stream Unified Red/Green Diffs with 1-Click Rollback**: Displays real-time unified line diffs with addition/deletion counters directly in chat whenever files are modified, accompanied by an instant **`[ ↺ Revert to .bak ]`** rollback button.
* **In-App Code Editor & Project Explorer**: View and edit code directly in the Right Panel with syntax highlighting, line numbers, and `Ctrl+S` live saving. Import external files from your PC with `[ 📥 Import Files ]` or reveal the folder in Windows File Explorer with `[ 📂 Reveal in Explorer ]`.
* **Pinned Chat Mode Bar & Zero-Scroll Composer**:
  * Pinned top-of-chat mode selector (`[ 💬 Chat ]`, `[ ⚡ Orchestrator ]`, `[ 🎨 Image Studio ]`) keeps mode context prominently visible.
  * Contextual controls (autonomy selector and image style picker) are housed right in the header, keeping the bottom composer clean, responsive, and completely free of horizontal scrolling on any screen size.
* **Message Branching & Autocomplete**:
  * `[ ✏️ Edit ]` on user messages truncates subsequent conversation turns to allow clean steering and branching.
  * Typing `@` in the composer brings up a fuzzy file picker to easily reference project files.

### 5. Zero-VRAM Gaming Mode & Hardware Auto-Tuner
* **Zero-VRAM Gaming Mode**: Offloads 100% of LLM execution to your system RAM (e.g. 64GB DDR5) so your discrete GPU (RTX 4070 SUPER) retains 100% dedicated VRAM and 0 FPS drops for modern games.
* **Sleep Mode (0 MB VRAM)**: One-click header button (`Sleep (0 VRAM)`) sends `keep_alive: 0` to Ollama and evicts all LLM and diffusion checkpoints from GPU memory. Automatically reloads models in ~1–2 seconds upon sending your next prompt.
* **Hardware Profiler**: Auto-detects host hardware at startup:
  * **Desktop**: NVIDIA RTX 4070 SUPER (12GB VRAM) + 64GB RAM — tunes for large context (`16,384`), CUDA Tensor acceleration, and strict VRAM handoff before diffusion.
  * **Laptop**: Intel Core Ultra 258V Lunar Lake + Arc 140V iGPU + AI Boost NPU + 32GB Shared RAM — tunes for unified memory and Mixture-of-Experts (MoE) models.

### 6. Mobile-First & WCAG 2.1 AA Accessibility
* **Touch-First Ergonomics**: All interactive buttons, dropdowns, and toggles adhere to a minimum touch target size of **44×44px** with `touch-action: manipulation;`.
* **Mobile Tap-to-Focus**: Root layout allows unrestricted text selection (`-webkit-user-select: text !important;`) ensuring immediate tap-to-focus on mobile textareas without keyboard dismissal conflicts.
* **Semantic ARIA Accordions**: Accessible `<button type="button">` accordions for tool traces, thinking drawers, and approval dialogs.

---

## Directory Structure

```
Local AI App/
├── backend/
│   ├── __init__.py
│   ├── agent.py            # Agent orchestrator, ReAct loop, tool permissions & approval events
│   ├── database.py         # aiosqlite layer (WAL mode, projects, conversations, artifacts, settings)
│   ├── hardware.py         # Hardware telemetry, silicon detection, and profile auto-tuning
│   ├── main.py             # FastAPI REST endpoints, SSE streaming, LAN guard, and file server
│   └── tools.py            # Shell execution, diff generator, safe backups, search, and document tools
├── frontend/
│   ├── dist/               # Production compiled bundle served by FastAPI
│   ├── src/
│   │   ├── components/     # Modular UI components
│   │   │   ├── AtMentionDropdown.jsx # In-composer @ project file autocomplete dropdown
│   │   │   ├── CodeEditorPanel.jsx   # In-app code editor with live save (Ctrl+S) and line counts
│   │   │   ├── DiffViewer.jsx        # Unified red/green file diff viewer with 1-click .bak revert
│   │   │   ├── SettingsModal.jsx     # 4-tab settings modal (Permissions, Hardware, Privacy, Phone Link)
│   │   │   ├── ToolApprovalCard.jsx  # Interactive in-stream approval card (Allow Once / Always / Deny)
│   │   │   └── WorkspaceModal.jsx    # Project creator (Managed Project vs Link PC Folder)
│   │   ├── App.jsx         # Primary React 18 workstation UI
│   │   ├── index.css       # Custom scrollbars, touch ergonomics, and typography
│   │   └── main.jsx        # React root entrypoint
│   ├── package.json        # Frontend dependencies (Lucide icons, Tailwind, Vite, marked)
│   └── vite.config.js      # Vite build configuration
├── bin/                    # Pre-compiled sd-cli.exe Vulkan binary (git ignored)
├── models/image/           # Local diffusion checkpoints (.safetensors) (git ignored)
├── workspace/
│   ├── artifacts/          # Generated output files, spreadsheets, and media (git ignored)
│   ├── projects/           # Managed local projects (git ignored)
│   └── uploads/            # Imported project files (git ignored)
├── scripts/
│   └── download_image_models.py # Helper script to fetch initial checkpoints
├── tests/
│   ├── test_learnings.py   # Unit test suite verifying confinement, router, and context compaction
│   └── test_search_live.py # Integration test verifying air-gap block and shielded web search
├── Launch-Studio.bat       # Windows batch launcher
├── Launch-Studio.vbs       # Silent background VBScript launcher (no flashing CMD window)
├── launcher.py             # Single-instance process manager and frameless browser app launcher
├── requirements.txt        # Python backend dependencies
├── AI_GUIDELINES.md        # Core engineering principles (Mobile-First, WCAG AA, Privacy, Git Hygiene)
└── README.md               # Project documentation
```

---

## Developer Quickstart

### Prerequisites
1. **Python 3.10+** (64-bit)
2. **Node.js 18+** & npm
3. **Ollama** installed on your system (`https://ollama.com`)
4. (Optional) Vulkan-compatible GPU for accelerated Stable Diffusion

### 1. Installation
Clone the repository:
```bash
git clone https://github.com/KetanaBlade/local-llm-app.git
cd local-llm-app
```

Install Python dependencies:
```bash
pip install -r requirements.txt
```

Install frontend dependencies and compile production bundle:
```bash
cd frontend
npm install
npm run build
cd ..
```

### 2. Pull Recommended Models
Start Ollama and pull fast, capable models:
```bash
ollama pull llama3.2:3b
ollama pull hermes3:8b
ollama pull qwen2.5-coder:7b
```

### 3. Launching the Studio
**Via Desktop Shortcut / Silent Launcher:**
Double-click `Launch-Studio.vbs` or run:
```bash
python launcher.py
```

**Via Standard Terminal:**
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) or open `http://<your-lan-ip>:8000` from your phone over local Wi-Fi.

---

## Running Automated Tests

Run the test suite verifying path boundary security, temporal grounding, diffusion model resolution, and air-gapped web search:

```bash
python -u tests/test_learnings.py
python -u tests/test_search_live.py
```

---

## Git & Privacy Hygiene

* **Zero External Telemetry**: No third-party analytics, external fonts, or cloud telemetry.
* **Residential IP Protection**: All web queries use Jina cloud reader proxies so target websites never log your home residential IP.
* **Zero Repository Pollution**: All `.db`, `.sqlite3`, `.db-wal`, `workspace/artifacts/`, and `models/` files are strictly excluded by `.gitignore`.
