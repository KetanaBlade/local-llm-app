"""
Download script for local diffusion models:
1. Realistic Vision V5.1 with baked VAE (Photorealism)
2. MeinaMix V11 (Anime/Manga)
Streams download with chunked progress reporting.
"""

import os
import sys
import time
from pathlib import Path
import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT_DIR / "models" / "image"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODELS = [
    {
        "name": "Realistic Vision V5.1 (Photorealism)",
        "filename": "realisticVisionV51_v51VAE.safetensors",
        "url": "https://huggingface.co/frankjoshua/realisticVisionV51_v51VAE/resolve/main/realisticVisionV51_v51VAE.safetensors",
        "expected_min_mb": 1800,
    },
    {
        "name": "MeinaMix V11 (Anime / Manga)",
        "filename": "meinamix_meinaV11.safetensors",
        "url": "https://huggingface.co/digiplay/MeinaMix_v11/resolve/main/meinamix_meinaV11.safetensors",
        "expected_min_mb": 1800,
    },
]


def download_file(item: dict):
    target = MODEL_DIR / item["filename"]
    if target.exists() and target.stat().st_size > item["expected_min_mb"] * 1024 * 1024:
        size_gb = target.stat().st_size / (1024**3)
        print(f"[SKIP] {item['name']} already exists at {target.name} ({size_gb:.2f} GB).", flush=True)
        return

    part_file = target.with_suffix(".part")
    print(f"\n[DOWNLOAD] Starting download for {item['name']}...", flush=True)
    print(f"URL: {item['url']}", flush=True)
    print(f"Destination: {target}", flush=True)

    headers = {"User-Agent": "LocalAIStudio/1.0 (Mozilla/5.0 compatible)"}
    try:
        with httpx.Client(timeout=1800.0, follow_redirects=True) as client:
            with client.stream("GET", item["url"], headers=headers) as resp:
                print(f"HTTP Response: {resp.status_code}", flush=True)
                if resp.status_code != 200:
                    print(f"[ERROR] HTTP {resp.status_code} fetching {item['name']}", flush=True)
                    return

                total_bytes = int(resp.headers.get("content-length", 0))
                downloaded = 0
                if part_file.exists():
                    downloaded = part_file.stat().st_size
                
                start_t = time.time()
                last_report_t = start_t

                mode = "ab" if downloaded > 0 else "wb"
                with open(part_file, mode) as f:
                    for chunk in resp.iter_bytes(chunk_size=1024 * 1024 * 4):  # 4MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if now - last_report_t >= 2.0:
                            last_report_t = now
                            elapsed = max(0.5, now - start_t)
                            speed_mb = ((downloaded - (part_file.stat().st_size if mode == 'ab' else 0)) / (1024 * 1024)) / elapsed
                            pct = (downloaded / total_bytes * 100) if total_bytes else 0
                            dl_mb = downloaded / (1024 * 1024)
                            tot_mb = total_bytes / (1024 * 1024) if total_bytes else 0
                            print(f"  -> {dl_mb:.1f} MB / {tot_mb:.1f} MB ({pct:.1f}%) @ {speed_mb:.1f} MB/s", flush=True)

        if part_file.exists():
            if part_file.stat().st_size > item["expected_min_mb"] * 1024 * 1024:
                if target.exists():
                    target.unlink()
                part_file.rename(target)
                print(f"[SUCCESS] Downloaded {item['name']} ({target.stat().st_size / (1024**3):.2f} GB)", flush=True)
            else:
                print(f"[ERROR] Downloaded file is too small ({part_file.stat().st_size} bytes)", flush=True)
    except Exception as exc:
        print(f"[EXCEPTION] Failed during download of {item['name']}: {exc}", flush=True)


if __name__ == "__main__":
    for m in MODELS:
        download_file(m)
    print("\n[COMPLETE] All requested image models ready in models/image/!", flush=True)
