# Local AI Studio — Universal On-Device Workstation

A 100% private, zero-telemetry, air-gapped local AI studio that combines a responsive conversational web interface with an autonomous **Antigravity Agent Engine**. Capable of generating live neural images, production-grade Excel spreadsheets (`.xlsx`) with formulas, formatted PDF/Word documents, interactive HTML/JS applications, and executing Python in a sandboxed runtime—completely on-device.

---

## Architecture Overview

```
                          ┌────────────────────────────────────────────────────────┐
                          │                Client Presentation Tier                │
                          │   React 18 + Tailwind CSS + Lucide Icons + Vite        │
                          │   (Desktop Web Browser / Frameless Edge App / Mobile)  │
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
│ - Llama 3.2 / Qwen 2.5    │ │ - CyberRealistic V8       │ │       Obliteration)       │ │  - reportlab / python-docx│
│ - Hardware-Tuned num_ctx  │ │ - MeinaMix V11 (Anime)    │ │ - Conversations & Context │ │  - Python Execution Box   │
│ - Zero-VRAM Auto-Eviction │ │ - DreamShaper 8 (Art)     │ │ - Artifact Tracking       │ │  - Workspace Confinement  │
└───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘
```

---

## Key Capabilities & Features

### 1. Multi-Model Neural Diffusion Router
Directly runs quantized Stable Diffusion checkpoints on local GPU VRAM via Vulkan compute:
* **CyberRealistic V8 FP16** (`CyberRealistic_V8_FP16.safetensors` • 1.99 GB): Tailored for DSLR photographic textures, human skin realism, macro shots, and realistic lighting with negative photographic prompts.
* **MeinaMix V11** (`meinamix_meinaV11.safetensors` • 1.99 GB): Fine-tuned anime, manga, and digital illustrative art.
* **DreamShaper 8** (`DreamShaper_8_pruned.safetensors` • 1.99 GB): Concept art, fantasy character designs, and 3D stylized landscapes.
* **Intelligent Aesthetic Router**: Evaluates user prompts (or explicit requests like *"Use CyberRealistic..."* or *"Draw an anime character with MeinaMix..."*) and routes to the matching engine, dynamically tailoring positive and negative prompt embeddings.
* **Real-time Status Streaming**: Emits live engine metadata over SSE so the UI displays the exact model actively rendering on your GPU.

### 2. Autonomous Agent & Document Synthesis
Equipped with native tool-calling capabilities that stream structured artifacts straight to the user:
* **Excel Spreadsheets (`.xlsx`)**: Generates real spreadsheets with alternating header styles, column width auto-fitting, number formatting, and functional dynamic formulas (`=SUM()`, `=AVERAGE()`).
* **Reports & Documents (`.pdf`, `.docx`)**: Formats clean typography reports, invoices, and executive summaries with download buttons and inline previews.
* **Interactive Web Apps (`.html`)**: Generates standalone single-file interactive tools (calculators, simulators, dashboard widgets) rendered in a sandboxed `<iframe>`.
* **Python Execution Sandbox**: Runs local Python scripts for computational tasks, mathematics, and data transformation within a confined working directory.
* **Optional DuckDuckGo Web Search**: User-controlled toggle between strict **Offline-Only / Air-Gap Mode** and live DuckDuckGo web synthesis with citation badges.

### 3. Odysseus-Inspired Reliability & Confinement
Incorporates core lessons from production agent architectures:
* **Path Confinement Boundary**: Strict traversal defenses (`confine_to_workspace()`) intercepting relative path escapes (`../../`), absolute root redirects, and NUL byte injections before any file I/O occurs.
* **Dynamic Date & Temporal Grounding**: Injects real-world calendar grounding into agent system prompts, preventing LLMs from assuming historic cutoff years for schedules, budgets, and current plans.
* **Cursor-Style Context Auto-Compaction**: Calculates running token estimates and compacts older conversation history into summarized anchors while preserving recent conversational turns verbatim.

### 4. Zero-VRAM Sleep Mode & Server Lifecycle
* **Sleep Mode (0 MB VRAM)**: One-click header button (`Sleep (0 VRAM)`) sends `keep_alive: 0` to Ollama and evicts all LLM and diffusion checkpoints from GPU memory. Frees 100% of your VRAM for gaming or video rendering. Automatically reloads models in ~1–2 seconds upon sending your next prompt.
* **In-App Shutdown**: Clean power-off button in the UI terminates background server processes and flushes all memory handles.
* **Single-Instance Windows Launcher (`launcher.py` / `Launch-Studio.vbs`)**: Double-clicking the desktop shortcut tests port 8000. If the server is already active, it simply opens the application window without spinning up duplicate background processes. Opens Microsoft Edge / Chrome in native `--app=http://localhost:8000` mode (frameless, zero address bar clutter).

### 5. Universal Hardware Auto-Tuner
Auto-inspects host silicon at startup and selects optimized runtime parameters:

| Profile | Hardware Environment | Auto-Tuned Strategy |
| :--- | :--- | :--- |
| **Desktop Workstation** | **NVIDIA RTX 4070 SUPER (12GB GDDR6X)** + 64GB RAM | `16,384` context window, CUDA Tensor Core acceleration, automated VRAM handoff before diffusion generation. Recommends `qwen2.5-coder:7b`, `llama3.2:3b`, `qwen2.5-coder:14b`. |
| **Thin & Light AI Laptop** | **Intel Core Ultra 258V** + **Intel Arc 140V iGPU** + **Intel AI Boost NPU (47 TOPS)** + 32GB RAM | Detects unified memory pool, selects `12,288` context window with `q8_0` KV cache, enables 5-minute idle unload for battery conservation, and recommends `qwen3:30b-a3b` MoE or `llama3.2:3b`. |

---

## Directory Structure

```
Local AI App/
├── backend/
│   ├── __init__.py
│   ├── agent.py            # Agent orchestrator, prompt compilation, SSE streaming & tool execution
│   ├── database.py         # aiosqlite layer (WAL mode, secure deletion, message history & artifact storage)
│   ├── hardware.py         # Hardware telemetry, silicon detection, and profile auto-tuning
│   ├── main.py             # FastAPI application, REST endpoints, LAN guard middleware, and static server
│   └── tools.py            # Multi-model diffusion router, openpyxl/reportlab builders, workspace boundary
├── frontend/
│   ├── dist/               # Production compiled bundle served by FastAPI
│   ├── src/
│   │   ├── App.jsx         # Primary React 18 application component (WCAG AA, mobile-first responsive)
│   │   ├── index.css       # Custom scrollbars, prose typography, and Tailwind definitions
│   │   └── main.jsx        # React root entrypoint
│   ├── package.json        # Frontend dependencies (Lucide icons, Tailwind, Vite, marked)
│   └── vite.config.js      # Vite build configuration
├── bin/                    # (Ignored in git) Pre-compiled sd-cli.exe Vulkan binary
├── models/image/           # (Ignored in git) Local diffusion checkpoints (.safetensors)
├── workspace/
│   ├── artifacts/          # (Ignored in git) Generated files, images, spreadsheets, and PDFs
│   └── projects/           # (Ignored in git) Multi-file projects created by the agent
├── scripts/
│   └── download_image_models.py # Helper script to fetch CyberRealistic V8 and MeinaMix checkpoints
├── tests/
│   └── test_learnings.py   # Unit test suite verifying confinement, router, and context compaction
├── Launch-Studio.bat       # Windows batch launcher
├── Launch-Studio.vbs       # Silent background VBScript launcher (no flashing CMD window)
├── launcher.py             # Single-instance process manager and frameless browser app launcher
├── create_desktop_shortcut.ps1 # Script that creates 'Local AI Studio.lnk' on the Windows Desktop
├── requirements.txt        # Python backend dependencies
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

Install frontend dependencies and build:
```bash
cd frontend
npm install
npm run build
cd ..
```

### 2. Pull Recommended Base Models
Start Ollama and pull standard models:
```bash
ollama pull llama3.2:3b
ollama pull qwen2.5-coder:7b
```

Download diffusion checkpoints (optional, for image generation):
```bash
python scripts/download_image_models.py
```

### 3. Launching the App
**Via Desktop Launcher (Windows):**
Double-click `Launch-Studio.vbs` or run:
```bash
python launcher.py
```

**Via Standard Terminal:**
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Running Automated Tests

Run the test suite verifying path boundary security, temporal grounding, diffusion model resolution, and artifact lifecycle management:

```bash
python -u tests/test_learnings.py
```

---

## Git & Privacy Hygiene

* **Zero Data Leakage**: All `.db`, `.sqlite3`, `.db-wal`, `workspace/artifacts/`, `workspace/projects/`, and `models/` files are explicitly excluded by `.gitignore`.
* **Zero External Telemetry**: The application sends zero tracking pings, metrics, or logs to external servers. All inference and artifact generation executes 100% locally.
