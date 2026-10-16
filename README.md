# Local AI Studio — Universal On-Device Antigravity Workstation

A 100% private, zero-telemetry local AI workstation combining a clean conversational interface with an autonomous **Antigravity Agent Engine** capable of creating formatted Excel spreadsheets (`.xlsx`), PDF & Word documents (`.pdf`, `.docx`), high-DPI charts, procedural visuals/animations, and interactive HTML/JS web applications.

---

## Quick Start

### 1. One-Click Launch (Windows)
Double-click [`start_studio.bat`](file:///c:/Users/Stardust/Documents/Local%20AI%20App/start_studio.bat) or run from PowerShell:
```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- **On Your PC:** Open `http://localhost:8000`
- **On Your Phone (Home Wi-Fi):** Open `http://192.168.1.151:8000` (or click the **LAN / Phone** button in the top bar to scan the QR code).

---

## Universal Hardware Auto-Tuner (Desktop & Laptop Ready)

At startup, [`backend/hardware.py`](file:///c:/Users/Stardust/Documents/Local%20AI%20App/backend/hardware.py) inspects your host CPU, GPU, NPU, and memory architecture:

| Hardware Profile | Detected Silicon | Auto-Tuned Strategy |
| :--- | :--- | :--- |
| **Desktop Workstation** | **NVIDIA RTX 4070 SUPER (12GB GDDR6X)** + 64GB RAM | `16,384` context window, CUDA Tensor Core acceleration, and automatic **VRAM Hand-Off** (`keep_alive: 0`) before launching local diffusion. Recommends `qwen2.5-coder:7b`, `qwen2.5-coder:14b`, and `llama3.1:8b`. |
| **Thin & Light AI Laptop** | **Intel Core Ultra 258V** + **Intel Arc 140V iGPU** + **Intel AI Boost NPU (47 TOPS)** + **32GB Unified LPDDR5X** | Detects unified memory (~17.6GB shared iGPU pool), sets `12,288` context window with `q8_0` KV cache and 5-minute battery-saving idle unload, and recommends **Mixture-of-Experts (`qwen3:30b-a3b`)** + `qwen2.5-coder:7b` + `llama3.2:3b`. |

> **Tip:** Click the **Silicon Telemetry Pill** in the top header at any time to switch between `Auto-Detect`, `Desktop: RTX 4070 SUPER`, and `Laptop: Core Ultra 258V` to preview how the engine adapts on either machine.
