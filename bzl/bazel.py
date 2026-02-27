"""Bazel query runner, output parser, and disk cache."""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Optional

from .ssh import SSHConfig

# ── Cache config ─────────────────────────────────────────────────────────────

_CACHE_DIR = Path.home() / ".cache" / "bzl"
_CACHE_VERSION = 1


def _cache_key(host: Optional[str], scope: str, kinds: list[str]) -> str:
    """Stable filename key based on (ssh-host, scope, kinds)."""
    kinds_str = ",".join(sorted(kinds))
    raw = f"{host or 'local'}:{scope}:{kinds_str}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cache_path(host: Optional[str], scope: str, kinds: list[str]) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{_cache_key(host, scope, kinds)}.json"


# ── Public cache API ──────────────────────────────────────────────────────────

class CacheEntry:
    """Wraps cached query results with metadata."""

    def __init__(self, targets: dict[str, list[str]], timestamp: float) -> None:
        self.targets = targets
        self.timestamp = timestamp

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    @property
    def age_str(self) -> str:
        s = int(self.age_seconds)
        if s < 60:
            return f"{s}s ago"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h {(s % 3600) // 60}m ago"
        days = s // 86400
        if days < 7:
            return f"{days}d ago"
        return f"{days // 7}w {days % 7}d ago"


def load_cache(host: Optional[str], scope: str, kinds: list[str], ttl_seconds: int) -> Optional[CacheEntry]:
    """
    Return a CacheEntry if a fresh cache exists, else None.
    Pass ttl_seconds=0 to skip the cache entirely.
    """
    if ttl_seconds <= 0:
        return None
    path = _cache_path(host, scope, kinds)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if data.get("version") != _CACHE_VERSION:
            return None
        age = time.time() - data["timestamp"]
        if age > ttl_seconds:
            return None
        return CacheEntry(
            targets=data["targets"],
            timestamp=data["timestamp"],
        )
    except Exception:
        return None


def save_cache(
    host: Optional[str],
    scope: str,
    kinds: list[str],
    targets: dict[str, list[str]],
) -> None:
    """Write query results to disk cache."""
    path = _cache_path(host, scope, kinds)
    try:
        path.write_text(json.dumps({
            "version": _CACHE_VERSION,
            "host": host or "local",
            "scope": scope,
            "kinds": kinds,
            "timestamp": time.time(),
            "targets": targets,
        }, indent=2))
    except Exception:
        pass  # cache write failure is non-fatal


def bust_cache(host: Optional[str], scope: str, kinds: list[str]) -> None:
    """Delete the cache file for this host+scope+kinds."""
    path = _cache_path(host, scope, kinds)
    path.unlink(missing_ok=True)


# ── Query runners ─────────────────────────────────────────────────────────────

def query_local(scope: str, kinds: list[str]) -> str:
    """Run bazel query locally and return raw stdout."""
    kind_expr = "|".join(kinds) if len(kinds) > 1 else kinds[0]
    cmd = ["bazel", "query", f"kind('{kind_expr}', {scope})"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "bazel query failed")
    return result.stdout


def query_ssh(ssh_config: SSHConfig, scope: str, kinds: list[str]) -> str:
    """Run bazel query on a remote host over SSH and return raw stdout."""
    cmd = ssh_config.build_query_cmd(scope, kinds)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "remote bazel query failed")
    return result.stdout


def query_all_kinds_local(scope: str) -> list[str]:
    """Get all unique rule kinds in the workspace."""
    cmd = ["bazel", "query", f"{scope}", "--output", "label_kind"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    kinds = set()
    for line in result.stdout.splitlines():
        if " " in line:
            kinds.add(line.split(" ")[0])
    return sorted(list(kinds))


def query_all_kinds_ssh(ssh_config: SSHConfig, scope: str) -> list[str]:
    """Get all unique rule kinds in the workspace via SSH."""
    cmd = ssh_config.build_all_kinds_query_cmd(scope)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    kinds = set()
    for line in result.stdout.splitlines():
        if " " in line:
            kinds.add(line.split(" ")[0])
    return sorted(list(kinds))


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_query_output(output: str) -> dict[str, list[str]]:
    """
    Parse bazel query output into {module: [rule_names]}.
    Each line looks like: //services/alerts:generate_swagger_client
    """
    from collections import defaultdict
    targets: dict[str, list[str]] = defaultdict(list)
    for line in output.splitlines():
        line = line.strip()
        if not line or not line.startswith("//"):
            continue
        if ":" not in line:
            continue
        module, rule = line.rsplit(":", 1)
        targets[module].append(rule)
    return {
        module: sorted(rules)
        for module, rules in sorted(targets.items())
    }
