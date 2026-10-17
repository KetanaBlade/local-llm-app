"""
Universal Hardware Profiler & Runtime Auto-Tuner.

Automatically detects host silicon topology across:
1. Discrete GPU Workstations (e.g., NVIDIA RTX 4070 SUPER 12GB VRAM + 64GB RAM)
2. Unified Memory AI Laptops (e.g., Intel Core Ultra 258V w/ Intel Arc 140V iGPU + Intel AI Boost NPU + 32GB LPDDR5X)
3. AMD ROCm / Vulkan & CPU-fallback systems

Computes optimal Ollama runtime flags (num_ctx, num_gpu, keep_alive),
VRAM hand-off policies for image/video generation, and curated model recommendations.
"""

from __future__ import annotations

import platform
import socket
import subprocess
from typing import Any, Dict, List, Optional

import psutil


def _run_cmd(cmd: List[str], timeout: float = 4.0) -> str:
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        )
        return res.stdout.strip() if res.returncode == 0 else ""
    except Exception:
        return ""


def get_lan_ip() -> str:
    """Resolve primary LAN IPv4 address for mobile phone access over Wi-Fi."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.1.1", 80))
            ip = s.getsockname()[0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass
    try:
        for iface, snics in psutil.net_if_addrs().items():
            if any(skip in iface.lower() for skip in ("loopback", "vethernet", "nord", "vpn", "bluetooth")):
                continue
            for snic in snics:
                if snic.family == socket.AF_INET and not snic.address.startswith(("127.", "169.254.")):
                    return snic.address
    except Exception:
        pass
    return "127.0.0.1"


def detect_nvidia_gpu() -> Optional[Dict[str, Any]]:
    """Query nvidia-smi for discrete NVIDIA GPU telemetry."""
    out = _run_cmd([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu,driver_version",
        "--format=csv,noheader,nounits",
    ])
    if not out:
        return None
    first_line = out.splitlines()[0]
    parts = [p.strip() for p in first_line.split(",")]
    if len(parts) < 6:
        return None
    try:
        total_mb = int(float(parts[1]))
        free_mb = int(float(parts[2]))
        used_mb = int(float(parts[3]))
        util_pct = int(float(parts[4])) if parts[4].isdigit() else 0
    except ValueError:
        return None
    return {
        "vendor": "NVIDIA",
        "name": parts[0],
        "vram_total_mb": total_mb,
        "vram_total_gb": round(total_mb / 1024, 1),
        "vram_free_mb": free_mb,
        "vram_free_gb": round(free_mb / 1024, 1),
        "vram_used_mb": used_mb,
        "gpu_utilization_pct": util_pct,
        "driver_version": parts[5],
        "backend": "CUDA 12 • Tensor Cores",
    }


def detect_windows_cpu_igpu_npu() -> Dict[str, Any]:
    """Inspect Windows WMI for CPU name, Intel Arc / AMD iGPU, and NPU accelerators."""
    cpu_name = platform.processor() or "Unknown CPU"
    gpus: List[str] = []
    npu_name: Optional[str] = None

    if platform.system() == "Windows":
        ps_script = (
            "$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name; "
            "$gpus = (Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }) -join '|'; "
            "$npu = (Get-CimInstance Win32_PnPEntity | Where-Object { "
            "$_.Name -match 'AI Boost|NPU|Neural|Hexagon|IPU' "
            "} | Select-Object -First 1).Name; "
            "Write-Output \"$cpu`n$gpus`n$npu\""
        )
        out = _run_cmd(["powershell", "-NoProfile", "-Command", ps_script], timeout=5.0)
        if out:
            lines = out.splitlines()
            if len(lines) >= 1 and lines[0].strip():
                cpu_name = lines[0].strip()
            if len(lines) >= 2 and lines[1].strip():
                gpus = [g.strip() for g in lines[1].split("|") if g.strip()]
            if len(lines) >= 3 and lines[2].strip():
                npu_name = lines[2].strip()

    # Check if CPU itself implies Intel Core Ultra Lunar Lake / Arrow Lake / Meteor Lake NPU
    cpu_lower = cpu_name.lower()
    if not npu_name and ("core ultra" in cpu_lower or "258v" in cpu_lower or "256v" in cpu_lower or "288v" in cpu_lower):
        npu_name = "Intel AI Boost NPU (47 TOPS)"

    return {
        "cpu_name": cpu_name,
        "gpus": gpus,
        "npu_name": npu_name,
    }


def build_hardware_profile(override_profile: str = "auto") -> Dict[str, Any]:
    """
    Build the complete hardware telemetry and auto-tuning profile.

    override_profile options:
    - "auto": Real-time hardware detection on current host
    - "desktop_rtx4070s": Force/preview Desktop NVIDIA RTX 4070 SUPER (12GB VRAM + 64GB RAM)
    - "laptop_ultra_258v": Force/preview Laptop Intel Core Ultra 7 258V (Arc 140V + 47 TOPS NPU + 32GB Unified RAM)
    """
    vm = psutil.virtual_memory()
    ram_total_gb = round(vm.total / (1024 ** 3), 1)
    ram_free_gb = round(vm.available / (1024 ** 3), 1)
    cpu_usage_pct = psutil.cpu_percent(interval=None)
    cpu_cores = psutil.cpu_count(logical=False) or 4
    cpu_threads = psutil.cpu_count(logical=True) or 8

    # Allow simulating the Intel Core Ultra 258V profile (or auto-detecting it when running on the laptop)
    if override_profile == "laptop_ultra_258v":
        return _profile_intel_lunar_lake(
            cpu_name="Intel Core Ultra 7 258V",
            igpu_name="Intel Arc 140V GPU (16GB Shared Unified Pool)",
            npu_name="Intel AI Boost NPU (47 INT8 TOPS)",
            ram_total_gb=32.0,
            ram_free_gb=24.2,
            cpu_cores=8,
            cpu_threads=8,
            cpu_usage_pct=cpu_usage_pct,
            is_simulated=True,
        )

    nvidia = detect_nvidia_gpu()
    sys_info = detect_windows_cpu_igpu_npu()
    cpu_name = sys_info["cpu_name"]
    all_gpus = sys_info["gpus"]
    npu_name = sys_info["npu_name"]

    # Check if host is actually an Intel Core Ultra Lunar Lake / Arc Unified system without discrete NVIDIA
    is_intel_arc = any("arc" in g.lower() or "intel(r) graphics" in g.lower() for g in all_gpus)
    is_core_ultra = "core ultra" in cpu_name.lower() or "258v" in cpu_name.lower()

    if (not nvidia and (is_intel_arc or is_core_ultra)) or override_profile == "intel_arc":
        arc_gpu_name = next((g for g in all_gpus if "arc" in g.lower()), "Intel Arc Integrated Graphics")
        return _profile_intel_lunar_lake(
            cpu_name=cpu_name,
            igpu_name=arc_gpu_name,
            npu_name=npu_name or "Intel AI Boost NPU",
            ram_total_gb=ram_total_gb,
            ram_free_gb=ram_free_gb,
            cpu_cores=cpu_cores,
            cpu_threads=cpu_threads,
            cpu_usage_pct=cpu_usage_pct,
            is_simulated=False,
        )

    if nvidia or override_profile == "desktop_rtx4070s":
        gpu_data = nvidia or {
            "vendor": "NVIDIA",
            "name": "NVIDIA GeForce RTX 4070 SUPER",
            "vram_total_mb": 12282,
            "vram_total_gb": 12.0,
            "vram_free_mb": 9940,
            "vram_free_gb": 9.7,
            "vram_used_mb": 2342,
            "gpu_utilization_pct": 4,
            "driver_version": "610.88",
            "backend": "CUDA 12 • Tensor Cores",
        }
        return _profile_nvidia_discrete(
            cpu_name=cpu_name,
            gpu_data=gpu_data,
            all_gpus=all_gpus,
            npu_name=npu_name,
            ram_total_gb=ram_total_gb,
            ram_free_gb=ram_free_gb,
            cpu_cores=cpu_cores,
            cpu_threads=cpu_threads,
            cpu_usage_pct=cpu_usage_pct,
            is_simulated=(override_profile == "desktop_rtx4070s" and nvidia is None),
        )

    # Generic Unified / CPU + iGPU fallback
    primary_gpu = all_gpus[0] if all_gpus else "Integrated Graphics / CPU"
    return {
        "profile_id": "universal_hybrid",
        "profile_label": "Universal Hybrid / Unified Memory",
        "short_badge": f"{primary_gpu} • {ram_total_gb}GB RAM",
        "is_simulated": False,
        "architecture_type": "Unified System Memory",
        "cpu": {
            "name": cpu_name,
            "cores": cpu_cores,
            "threads": cpu_threads,
            "usage_pct": cpu_usage_pct,
        },
        "gpu": {
            "vendor": "Integrated",
            "name": primary_gpu,
            "memory_type": "Shared System RAM",
            "vram_total_gb": round(ram_total_gb * 0.5, 1),
            "vram_free_gb": round(ram_free_gb * 0.5, 1),
            "utilization_pct": 0,
            "backend": "Vulkan / CPU AVX2",
        },
        "npu": {
            "present": bool(npu_name),
            "name": npu_name or "None detected",
            "role": "Background embeddings & low-power inference" if npu_name else "N/A",
        },
        "memory": {
            "ram_total_gb": ram_total_gb,
            "ram_free_gb": ram_free_gb,
            "unified_memory": True,
        },
        "tuning": {
            "recommended_num_ctx": 8192,
            "vram_handoff_before_media": False,
            "keep_alive": "10m",
            "flash_attention": True,
            "kv_cache_quant": "q8_0",
            "explanation": (
                "Balanced unified memory policy. Models use shared system RAM with 8K context "
                "window to preserve system responsiveness."
            ),
        },
        "recommended_models": _get_universal_models(),
        "lan_ip": get_lan_ip(),
    }


def _profile_nvidia_discrete(
    cpu_name: str,
    gpu_data: Dict[str, Any],
    all_gpus: List[str],
    npu_name: Optional[str],
    ram_total_gb: float,
    ram_free_gb: float,
    cpu_cores: int,
    cpu_threads: int,
    cpu_usage_pct: float,
    is_simulated: bool,
) -> Dict[str, Any]:
    vram_total = gpu_data["vram_total_gb"]
    vram_free = gpu_data["vram_free_gb"]
    short_gpu = gpu_data["name"].replace("NVIDIA GeForce ", "")

    return {
        "profile_id": "desktop_rtx4070s",
        "profile_label": f"Discrete CUDA Workstation ({short_gpu})",
        "short_badge": f"{short_gpu} • {vram_free}GB Free VRAM",
        "is_simulated": is_simulated,
        "architecture_type": "Discrete GDDR6X VRAM + High-Capacity System RAM",
        "cpu": {
            "name": cpu_name,
            "cores": cpu_cores,
            "threads": cpu_threads,
            "usage_pct": cpu_usage_pct,
        },
        "gpu": {
            "vendor": "NVIDIA",
            "name": gpu_data["name"],
            "memory_type": "Dedicated GDDR6X VRAM (504 GB/s)",
            "vram_total_gb": vram_total,
            "vram_free_gb": vram_free,
            "utilization_pct": gpu_data.get("gpu_utilization_pct", 0),
            "backend": gpu_data["backend"],
            "driver": gpu_data.get("driver_version", ""),
            "secondary_gpus": [g for g in all_gpus if "nvidia" not in g.lower()],
        },
        "npu": {
            "present": bool(npu_name),
            "name": npu_name or "Not present (Discrete Tensor Cores active)",
            "role": "CUDA Tensor Cores handle all LLM & Diffusion acceleration",
        },
        "memory": {
            "ram_total_gb": ram_total_gb,
            "ram_free_gb": ram_free_gb,
            "unified_memory": False,
        },
        "tuning": {
            "recommended_num_ctx": 8192,
            "vram_handoff_before_media": True,
            "keep_alive": "3m",
            "flash_attention": True,
            "kv_cache_quant": "q8_0",
            "explanation": (
                f"Detected {vram_total}GB dedicated VRAM ({vram_free}GB free) + {ram_total_gb}GB system RAM. "
                "Single-Model VRAM Lock is ENABLED: switching models or starting a new chat automatically "
                "evicts prior models from VRAM, and idle models unload after 3 minutes."
            ),
        },
        "recommended_models": [
            {
                "id": "llama3.2:3b",
                "name": "Llama 3.2 3B",
                "size_gb": 2.0,
                "fit": "100% VRAM (Ultra Fast ~120 tok/s)",
                "role": "Snappy Lightweight Chat & Instant Answers",
                "badge": "Lightning Fast",
                "recommended": True,
            },
            {
                "id": "hermes3:8b",
                "name": "Hermes 3 8B (Nous Research)",
                "size_gb": 4.7,
                "fit": "100% VRAM (Fast ~80 tok/s)",
                "role": "Creative Writing, Fiction & Expressive Dialogue",
                "badge": "Creative Writing",
                "recommended": True,
            },
            {
                "id": "mistral-nemo:12b",
                "name": "Mistral NeMo 12B (NVIDIA + Mistral)",
                "size_gb": 7.1,
                "fit": "100% VRAM (~48 tok/s)",
                "role": "Literary Fiction, Long-form Prose & 128k Memory",
                "badge": "Extended Context",
                "recommended": True,
            },
            {
                "id": "qwen2.5-coder:7b",
                "name": "Qwen 2.5 Coder 7B",
                "size_gb": 4.7,
                "fit": "100% VRAM (~75 tok/s)",
                "role": "Fast Agentic Coding, Excel & App Builder",
                "badge": "Best Tool Use",
                "recommended": True,
            },
            {
                "id": "qwen2.5-coder:14b",
                "name": "Qwen 2.5 Coder 14B",
                "size_gb": 9.0,
                "fit": "100% VRAM (~42 tok/s)",
                "role": "Deep Antigravity Coding & Architecture",
                "badge": "Max Intelligence",
                "recommended": True,
            },
            {
                "id": "deepseek-r1:8b",
                "name": "DeepSeek-R1 8B (Reasoning)",
                "size_gb": 4.9,
                "fit": "100% VRAM (~65 tok/s)",
                "role": "Step-by-step Chain-of-Thought Logic & Math",
                "badge": "Reasoning",
                "recommended": False,
            },
            {
                "id": "qwen3:30b-a3b",
                "name": "Qwen 3 30B-A3B (MoE)",
                "size_gb": 18.0,
                "fit": "Hybrid (12GB VRAM + 64GB RAM Spillover)",
                "role": "Frontier 30B Knowledge with only 3B Active Params/Token",
                "badge": "Hybrid MoE",
                "recommended": False,
            },
        ],
        "lan_ip": get_lan_ip(),
    }


def _profile_intel_lunar_lake(
    cpu_name: str,
    igpu_name: str,
    npu_name: str,
    ram_total_gb: float,
    ram_free_gb: float,
    cpu_cores: int,
    cpu_threads: int,
    cpu_usage_pct: float,
    is_simulated: bool,
) -> Dict[str, Any]:
    shared_vram_gb = round(ram_total_gb * 0.55, 1)  # Windows allocates up to ~55-57% of 32GB (~17.6GB) to Arc 140V
    shared_free_gb = round(min(shared_vram_gb, ram_free_gb * 0.7), 1)

    return {
        "profile_id": "laptop_ultra_258v",
        "profile_label": "Intel Lunar Lake Unified AI Architecture (258V)",
        "short_badge": f"Core Ultra 258V • Arc + NPU • {int(ram_total_gb)}GB Unified",
        "is_simulated": is_simulated,
        "architecture_type": "On-Package Unified LPDDR5X-8533 + Arc Xe2 iGPU + 47 TOPS NPU",
        "cpu": {
            "name": cpu_name,
            "cores": cpu_cores,
            "threads": cpu_threads,
            "usage_pct": cpu_usage_pct,
        },
        "gpu": {
            "vendor": "Intel",
            "name": igpu_name,
            "memory_type": "Unified On-Package LPDDR5X-8533 (~136 GB/s)",
            "vram_total_gb": shared_vram_gb,
            "vram_free_gb": shared_free_gb,
            "utilization_pct": 8 if is_simulated else 0,
            "backend": "Intel Arc Xe2 (Vulkan / SYCL XMX) + DirectML",
        },
        "npu": {
            "present": True,
            "name": npu_name,
            "role": "Offloads embeddings, continuous background tasks & OpenVINO NPU pipelines for battery efficiency",
        },
        "memory": {
            "ram_total_gb": ram_total_gb,
            "ram_free_gb": ram_free_gb,
            "unified_memory": True,
        },
        "tuning": {
            "recommended_num_ctx": 12288,
            "vram_handoff_before_media": False,
            "keep_alive": "5m",
            "flash_attention": True,
            "kv_cache_quant": "q8_0",
            "explanation": (
                f"Detected Intel Core Ultra 258V with {int(ram_total_gb)}GB soldered LPDDR5X unified memory "
                f"(~{shared_vram_gb}GB addressable by Intel Arc 140V Xe2 XMX engines) + {npu_name}. "
                "Because memory bandwidth (~136 GB/s) is the primary bottleneck on thin-and-light laptops "
                "while total capacity is generous, the tuner prioritizes Mixture-of-Experts (MoE) models "
                "(like Qwen3 30B-A3B which activates only 3B parameters per token!) and compact 7B–8B dense models "
                "with Q8_0 quantized KV cache and 5-minute idle unload to save battery."
            ),
        },
        "recommended_models": [
            {
                "id": "qwen2.5-coder:7b",
                "name": "Qwen 2.5 Coder 7B",
                "size_gb": 4.7,
                "fit": "Arc Xe2 iGPU (~32–40 tok/s)",
                "role": "Primary Laptop Agentic Coding, Excel & Document Builder",
                "badge": "Best for Arc 140V",
                "recommended": True,
            },
            {
                "id": "qwen3:30b-a3b",
                "name": "Qwen 3 30B-A3B (Mixture-of-Experts)",
                "size_gb": 17.5,
                "fit": "Fits in 32GB Unified RAM (Only 3B active params/tok!)",
                "role": "High-Intelligence Reasoning & Coding at 3B Bandwidth Speed",
                "badge": "Lunar Lake MoE Secret Weapon",
                "recommended": True,
            },
            {
                "id": "llama3.2:3b",
                "name": "Llama 3.2 3B Instruct",
                "size_gb": 2.0,
                "fit": "Arc iGPU / NPU (~65+ tok/s, Ultra Low Wattage)",
                "role": "Battery-Saver Instant Chat & Quick Summaries",
                "badge": "Battery Saver",
                "recommended": True,
            },
            {
                "id": "llama3.1:8b",
                "name": "Llama 3.1 8B Instruct",
                "size_gb": 4.9,
                "fit": "Arc Xe2 iGPU (~30 tok/s)",
                "role": "Full-Featured General Chat & Creative Writing",
                "badge": "General Chat",
                "recommended": True,
            },
            {
                "id": "deepseek-r1:8b",
                "name": "DeepSeek-R1 8B",
                "size_gb": 4.9,
                "fit": "Arc Xe2 iGPU (~28 tok/s)",
                "role": "Offline Deep Reasoning & Analytical Problem Solving",
                "badge": "Reasoning",
                "recommended": False,
            },
        ],
        "lan_ip": get_lan_ip(),
    }


def _get_universal_models() -> List[Dict[str, Any]]:
    return [
        {
            "id": "qwen2.5-coder:7b",
            "name": "Qwen 2.5 Coder 7B",
            "size_gb": 4.7,
            "fit": "Universal GPU/Unified RAM",
            "role": "Agentic Coding & Tool Execution",
            "badge": "Recommended",
            "recommended": True,
        },
        {
            "id": "llama3.2:3b",
            "name": "Llama 3.2 3B Instruct",
            "size_gb": 2.0,
            "fit": "Fast Lightweight",
            "role": "General Chat & Quick Q&A",
            "badge": "Lightweight",
            "recommended": True,
        },
    ]
