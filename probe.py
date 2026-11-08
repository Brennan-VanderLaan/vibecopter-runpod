#!/usr/bin/env python3
"""Read-only diagnostics; CPU Vulkan must never count as GPU acceptance."""
import json
import os
import platform
import subprocess
from pathlib import Path


def command(args):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=30, check=False)
        return {"exit_code": p.returncode, "output": p.stdout}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"exit_code": -1, "output": str(e)}


def hardware_vulkan(summary):
    # Require the selected first Vulkan device to be a physical NVIDIA device.
    # A second NVIDIA device alongside CPU llvmpipe must not bless a CPU run.
    first = summary.split("GPU0:", 1)
    if len(first) != 2:
        return False
    device = first[1].split("GPU1:", 1)[0].lower()
    return ("0x10de" in device and
            ("physical_device_type_discrete_gpu" in device or
             "physical_device_type_integrated_gpu" in device) and
            not any(x in device for x in ("llvmpipe", "lavapipe", "swiftshader")))


def probe():
    gpu = command(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv"])
    vk = command(["vulkaninfo", "--summary"])
    rev = Path('/opt/vibecopter/image-revision')
    return {"schema": 1, "os": platform.platform(), "architecture": platform.machine(),
            "image_revision": rev.read_text().strip() if rev.exists() else "local",
            "image_reference": os.environ.get("TESTBOX_IMAGE_REFERENCE", "UNRECORDED"),
            "driver_capabilities": os.environ.get("NVIDIA_DRIVER_CAPABILITIES"),
            "nvidia": gpu, "vulkan": vk,
            "gpu_preflight_pass": gpu['exit_code'] == 0 and vk['exit_code'] == 0
                                  and hardware_vulkan(vk['output'])}


if __name__ == '__main__':
    print(json.dumps(probe(), indent=2))
