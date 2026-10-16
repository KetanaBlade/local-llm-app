# AI Engineering & Project Guidelines (`AI_GUIDELINES.md`)

This document establishes the core architectural, accessibility, privacy, and engineering standards for **Local AI Studio**. Every feature, module, and commit must adhere to these principles.

---

## 1. Mobile-First & Responsive Design
- **Touch-First Ergonomics:** All interactive elements (buttons, model selectors, artifact cards, toggles) must have a minimum touch target of **44×44px**.
- **Adaptive Viewports:** Layout must scale fluidly from small mobile screens (`320px–480px` accessed over LAN Wi-Fi) to tablets and widescreen desktop monitors (`1920px+`).
- **Collapsible Drawers:** Sidebars (Chat History and Workspace/Artifacts) must collapse into slide-over drawers on mobile screens to preserve vertical reading space.
- **PWA Ready:** Provide web manifest metadata so the app can be installed to a mobile home screen over the local network.

## 2. Accessibility (WCAG 2.1 AA Compliance)
- **Color Contrast:** Maintain a minimum contrast ratio of **4.5:1** for normal text and **3:1** for large text and UI components.
- **Keyboard & Screen Reader Navigation:** All modals, dropdowns, and tool-trace accordions must be operable via keyboard (`Tab`, `Enter`, `Escape`) and include semantic ARIA labels (`aria-label`, `aria-expanded`, `role="status"`).
- **Visible Focus States:** Never remove focus outlines without providing a high-contrast custom `:focus-visible` indicator.

## 3. Universal Hardware Agnosticism (Desktop & Laptop Portability)
- **Zero Hardcoded Hardware Assumptions:** The application must dynamically profile the host hardware at startup (`NVIDIA CUDA`, `Intel Core Ultra Arc iGPU + AI Boost NPU`, `AMD ROCm/Vulkan`, or `CPU`).
- **Adaptive Memory Management:**
  - **Discrete VRAM Profile (e.g., RTX 4070 SUPER 12GB):** Enforce strict VRAM hand-off (`keep_alive: 0`) before launching heavy secondary GPU workloads (image/video generation) and tune context window (`num_ctx`) to fit free VRAM without unwanted PCIe spillover.
  - **Unified Memory Profile (e.g., Intel Core Ultra 258V w/ 32GB LPDDR5X + Arc + NPU):** Leverage the shared memory pool (~16–18GB usable iGPU memory) to recommend Mixture-of-Experts (MoE) models (e.g., `qwen3:30b-a3b`) and efficient dense models (`qwen2.5-coder:7b/14b`, `phi4`), while routing lightweight background tasks to NPU/CPU where supported.
- **One-Command Portability:** Moving the project between PCs must require zero manual config edits.

## 4. Strict Privacy & Air-Gap Architecture
- **100% Local Data Residency:** Prompts, chat history, uploaded files, and generated artifacts are stored exclusively in local storage (`SQLite` and local `workspace/` directory).
- **Zero External Telemetry:** No third-party analytics, external tracking scripts, or cloud font CDNs that leak IP metadata when Air-Gap Mode is enabled.
- **Enforced Air-Gap Switch:** When **Strict Air-Gap Mode** is active (default), the backend blocks any outbound internet tool requests and restricts network communication strictly to `127.0.0.1` and local LAN subnets (`192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`).

## 5. DRY (Don't Repeat Yourself) & Modularity
- **Single Source of Truth:** Hardware profiles, tool schemas, and system prompts are defined once in dedicated backend modules and exposed to the frontend via typed REST endpoints.
- **Unified Tool Interface:** Every agent tool (Excel generator, Word/PDF builder, Code sandbox, File manager, Media generator) follows a standardized execution contract returning `{ status, output, artifacts[] }`.

## 6. Git Hygiene & Atomic Commits
- **Atomic Commits:** Group logically related changes into clear, self-contained commits using conventional commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`).
- **Clean Repository:** Never commit virtual environments (`.venv/`), `node_modules/`, SQLite databases (`*.db`), or user-generated artifacts (`workspace/artifacts/`).
