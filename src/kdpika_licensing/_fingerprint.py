"""Best-effort OS identifiers. Only product-salted hashes leave this module.

Identifiers are not an attestation: patched clients/VMs can spoof them. No raw
identifier is logged, persisted, or used as the random installation ID.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from pathlib import Path
from typing import Any


class HardwareUnavailable(Exception):
    """No usable component could be collected (no raw OS errors retained)."""


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as stream:
            return stream.read(65536).strip()
    except OSError:
        return ""


def _run(*command: str) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=4, check=False)
        return result.stdout[:65536].strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return ""


def _usable(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = re.sub(r"\s+", " ", value.strip().lower())
    if not value or len(value) > 1024 or value in {
        "unknown", "none", "default string", "to be filled by o.e.m.",
        "system serial number", "not specified", "not applicable",
    } or re.fullmatch(r"[0f:\- ]+", value):
        return ""
    return value


def hash_components(product: str, raw: dict[str, str], is_virtual: bool | None = None) -> dict[str, Any]:
    salt = hashlib.sha256(("kdpika-hardware-v1|" + product).encode()).hexdigest()
    components = {}
    for name in sorted(raw):
        value = _usable(raw[name])
        if name in {"baseboard", "cpu", "disk", "nic", "machine"} and value:
            components[name] = hashlib.sha256((salt + "|" + name + "|" + value).encode()).hexdigest()
    if not set(components) - {"cpu"}:
        raise HardwareUnavailable("Device information is unavailable.")
    combined = "\n".join(name + "=" + value for name, value in components.items())
    return {"version": 1, "hardware_id": hashlib.sha256(combined.encode()).hexdigest(),
            "components": components, "is_virtual": is_virtual}


def collect_fingerprint(product: str) -> dict[str, Any]:
    system = platform.system()
    raw: dict[str, str] = {}
    virtual_text = ""
    if system == "Windows":
        # Fixed commands, no shell or caller values. CIM replaces obsolete WMIC.
        command = """$ErrorActionPreference='SilentlyContinue';
        $board=(Get-CimInstance Win32_BaseBoard | Select-Object -First 1).SerialNumber;
        $cpu=(Get-CimInstance Win32_Processor | Select-Object -First 1).ProcessorId;
        $machine=(Get-CimInstance Win32_ComputerSystemProduct | Select-Object -First 1).UUID;
        $disk=(Get-Partition -DriveLetter $env:SystemDrive.Substring(0,1) | Get-Disk | Select-Object -First 1).SerialNumber;
        $nic=(Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Sort-Object InterfaceIndex | Select-Object -First 1).MacAddress;
        $model=(Get-CimInstance Win32_ComputerSystem).Model;
        @{baseboard=$board;cpu=$cpu;machine=$machine;disk=$disk;nic=$nic;model=$model} | ConvertTo-Json -Compress"""
        try:
            data = json.loads(_run("powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command))
            if isinstance(data, dict):
                raw = {name: data.get(name, "") for name in ("baseboard", "cpu", "disk", "nic")}
                if not _usable(raw.get("baseboard")):
                    raw["machine"] = data.get("machine", "")
                virtual_text = str(data.get("model", ""))
        except (ValueError, TypeError):
            pass
    elif system == "Darwin":
        registry = _run("/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice")
        match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"\n]+)"', registry)
        raw["baseboard"] = match.group(1) if match else ""
        raw["cpu"] = _run("/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string") or _run("/usr/sbin/sysctl", "-n", "hw.model")
        # IOPlatformUUID is the stable anchor; no privileged serial extraction.
        network = _run("/sbin/ifconfig", "en0")
        match = re.search(r"\bether\s+([0-9a-fA-F:]{17})", network)
        raw["nic"] = match.group(1) if match else ""
        virtual_text = registry
    elif system == "Linux":
        raw["baseboard"] = _read("/sys/class/dmi/id/board_serial") or _read("/sys/class/dmi/id/product_uuid")
        if not _usable(raw["baseboard"]):
            raw["machine"] = _read("/etc/machine-id") or _read("/var/lib/dbus/machine-id")
        cpu = _read("/proc/cpuinfo")
        match = re.search(r"^(?:model name|Hardware|Serial)\s*:\s*(.+)$", cpu, re.MULTILINE)
        raw["cpu"] = match.group(1) if match else platform.machine()
        try:
            for device in sorted(Path("/sys/class/block").iterdir()):
                if device.name.startswith(("loop", "ram", "dm-", "sr")) or (device / "partition").exists():
                    continue
                serial = _read(str(device / "device/serial"))
                if _usable(serial):
                    raw["disk"] = serial
                    break
            for interface in sorted(Path("/sys/class/net").iterdir()):
                if not (interface / "device").exists() or _read(str(interface / "operstate")) != "up":
                    continue
                raw["nic"] = _read(str(interface / "address"))
                break
        except OSError:
            pass
        virtual_text = _read("/sys/class/dmi/id/product_name") + " " + _read("/sys/class/dmi/id/sys_vendor")
    else:
        raise HardwareUnavailable("Device information is unavailable.")
    hint = bool(re.search(r"vmware|virtualbox|virtual machine|qemu|kvm|parallels|xen", virtual_text, re.I))
    return hash_components(product, raw, hint if virtual_text else None)


def matches_binding(binding: Any, current: dict[str, Any]) -> bool:
    """Check signed server policy locally, including cached/offline decisions."""
    if not isinstance(binding, dict) or not isinstance(binding.get("version"), int) or isinstance(binding["version"], bool) or binding["version"] != 1:
        return False
    saved, policy = binding.get("components"), binding.get("policy")
    if not isinstance(saved, dict) or not saved or not isinstance(policy, dict):
        return False
    if any(name not in {"baseboard", "cpu", "disk", "nic", "machine"}
           or not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value)
           for name, value in saved.items()):
        return False
    combined = hashlib.sha256("\n".join(name + "=" + saved[name] for name in sorted(saved)).encode()).hexdigest()
    if binding.get("hardware_id") != combined:
        return False
    actual = current["components"]
    if policy.get("mode") == "strict":
        return saved == actual
    if policy.get("mode") != "fuzzy":
        return False
    if any(name in saved and saved[name] != actual.get(name) for name in ("baseboard", "cpu")):
        return False
    minimum = policy.get("min_matches")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or not 1 <= minimum <= 5:
        return False
    return sum(value == actual.get(name) for name, value in saved.items()) >= min(len(saved), minimum)
