"""Entry point — parses args (with .bzlrc support), runs bazel query, launches TUI, exec's bazel."""
from __future__ import annotations

import argparse
import configparser
import fcntl
import os
import sys
import termios
from pathlib import Path
from typing import Optional

from .bazel import (
    query_local, query_ssh, parse_query_output,
    load_cache, save_cache, bust_cache,
)
from .ssh import SSHConfig
from .app import BzlApp

_DEFAULT_TTL_MINUTES = 20160  # 2 weeks


# ── .bzlrc handler ────────────────────────────────────────────────────────────



def _get_bzlrc_path() -> Path:
    """Find the best .bzlrc to write to: repo root if it exists, else home."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "WORKSPACE").exists() or (parent / "MODULE.bazel").exists():
            repo_rc = parent / ".bzlrc"
            if repo_rc.exists():
                return repo_rc
            break
    return Path.home() / ".bzlrc"


def _load_bzlrc() -> dict[str, str]:
    cfg = configparser.ConfigParser()
    candidates: list[Path] = []

    home_rc = Path.home() / ".bzlrc"
    if home_rc.exists():
        candidates.append(home_rc)

    cwd = Path.cwd()
    repo_rc = None
    for parent in [cwd, *cwd.parents]:
        if (parent / "WORKSPACE").exists() or (parent / "MODULE.bazel").exists():
            repo_rc = parent / ".bzlrc"
            if repo_rc.exists():
                candidates.append(repo_rc)
            break

    cfg.read(candidates)
    return dict(cfg["defaults"]) if cfg.has_section("defaults") else {}


def save_kinds_to_bzlrc(kinds: list[str]) -> None:
    """Save the selected kinds to the closest .bzlrc file."""
    path = _get_bzlrc_path()
    cfg = configparser.ConfigParser()
    if path.exists():
        cfg.read(path)
    
    if not cfg.has_section("defaults"):
        cfg.add_section("defaults")
    
    cfg.set("defaults", "kinds", ",".join(kinds))
    
    with open(path, "w") as f:
        cfg.write(f)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    rc = _load_bzlrc()

    parser = argparse.ArgumentParser(
        prog="bzl",
        description="bzl — Terminal UI for browsing and executing Bazel targets.",
        epilog=(
            "Examples:\n"
            "  # Run locally with default scope (//...)\n"
            "  bzl\n\n"
            "  # Run locally with a specific scope\n"
            "  bzl -S //src/main/...\n\n"
            "  # Run on a remote build server\n"
            "  bzl -s user@build-server -d /path/to/repo/on/remote\n\n"
            "  # Force a fresh Bazel query by bypassing the cache\n"
            "  bzl --no-cache\n\n"
            "Configuration (.bzlrc):\n"
            "  You can create a .bzlrc file in your repo root or ~/.bzlrc to set defaults.\n"
            "  Example .bzlrc:\n"
            "    [defaults]\n"
            "    ssh = user@build-server\n"
            "    ssh_dir = /home/user/my-repo\n"
            "    scope = //modules/...\n"
            "    cache_ttl = 20160"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s", "--ssh", metavar="USER@HOST",
        default=rc.get("ssh"),
        help="Run query and build on a remote host over SSH",
    )
    parser.add_argument(
        "-d", "--ssh-dir", metavar="PATH",
        default=rc.get("ssh_dir"),
        help="Working directory on the remote host (default: mirrors local cwd)",
    )
    parser.add_argument(
        "-S", "--scope", default=rc.get("scope", "//..."), metavar="PATTERN",
        help="Bazel query scope (default: %(default)s)",
    )
    parser.add_argument(
        "-c", "--cache-ttl", type=int,
        default=int(rc.get("cache_ttl", _DEFAULT_TTL_MINUTES)),
        metavar="MINUTES",
        help=f"Cache TTL in minutes (default: {_DEFAULT_TTL_MINUTES}). Use 0 to disable.",
    )
    parser.add_argument(
        "-n", "--no-cache", action="store_true",
        help="Bypass cache and force a fresh Bazel query",
    )
    args = parser.parse_args()

    # ── SSH config ────────────────────────────────────────────────────────────
    ssh_config: Optional[SSHConfig] = None
    if args.ssh:
        ssh_config = SSHConfig.from_args(args.ssh, args.ssh_dir)
        if not args.ssh_dir and not rc.get("ssh_dir"):
            print(
                f"⚠️   No --ssh-dir set. Assuming remote dir = {os.getcwd()}\n"
                f"    If wrong, pass --ssh-dir /path/on/remote or add ssh_dir = ... to .bzlrc",
                file=sys.stderr,
            )

    host_key = ssh_config.host if ssh_config else None
    ttl_seconds = 0 if args.no_cache else args.cache_ttl * 60
    host_key = ssh_config.host if ssh_config else None
    ttl_seconds = 0 if args.no_cache else args.cache_ttl * 60
    
    rc_kinds = rc.get("kinds", "genrule").split(",")
    kinds = [k.strip() for k in rc_kinds if k.strip()]

    # ── Try cache first ───────────────────────────────────────────────────────
    cached = load_cache(host_key, args.scope, kinds, ttl_seconds)
    if cached:
        print(
            f"⚡  Using cached results ({cached.age_str})  "
            f"— press ctrl+f inside bzl to refresh",
            flush=True,
        )
        targets = cached.targets
    else:
        where = f"ssh {ssh_config.host}" if ssh_config else "local"
        print(f"🔍  Querying Bazel ({where}, scope: {args.scope}) …", flush=True)
        try:
            if ssh_config:
                output = query_ssh(ssh_config, args.scope, kinds)
            else:
                output = query_local(args.scope, kinds)
        except Exception as exc:
            print(f"❌  Bazel query failed: {exc}", file=sys.stderr)
            if ssh_config and "No such file or directory" in str(exc):
                print(
                    f"\n💡  Hint: the remote dir '{ssh_config.remote_dir}' doesn't exist on {ssh_config.host}.\n"
                    f"    Find the right path with:\n"
                    f"      ssh {ssh_config.host} \"find ~ -maxdepth 4 -name WORKSPACE -o -name MODULE.bazel 2>/dev/null\"\n"
                    f"    Then re-run:\n"
                    f"      bzl --ssh {ssh_config.host} --ssh-dir /path/on/remote\n"
                    f"    Or set it permanently in .bzlrc:\n"
                    f"      echo '[defaults]' >> .bzlrc\n"
                    f"      echo 'ssh = {ssh_config.host}' >> .bzlrc\n"
                    f"      echo 'ssh_dir = /path/on/remote' >> .bzlrc",
                    file=sys.stderr,
                )
            sys.exit(1)

        targets = parse_query_output(output)
        if not targets:
            print("No targets found.", file=sys.stderr)
            sys.exit(1)

        save_cache(host_key, args.scope, kinds, targets)

    # ── Launch TUI ────────────────────────────────────────────────────────────
    app = BzlApp(
        targets=targets,
        ssh_config=ssh_config,
        scope=args.scope,
        kinds=kinds,
        on_kinds_change=save_kinds_to_bzlrc,
        cache_key=host_key,
        cache_ttl_seconds=ttl_seconds,
    )
    result = app.run()

    if result is None:
        sys.exit(0)

    target, verb = result

    # ── Print and exec ────────────────────────────────────────────────────────
    if not target:
        if ssh_config:
            exec_args = ssh_config.build_exec_args(None, verb)
            display_cmd = (
                f"ssh -t {ssh_config.host} "
                f"'cd {ssh_config.remote_dir} && bazel {verb}'"
            )
        else:
            exec_args = ["bazel", *verb.split()]
            display_cmd = f"bazel {verb}"
    else:
        if ssh_config:
            exec_args = ssh_config.build_exec_args(target, verb)
            display_cmd = (
                f"ssh -t {ssh_config.host} "
                f"'cd {ssh_config.remote_dir} && bazel {verb} {target}'"
            )
        else:
            exec_args = ["bazel", verb, target]
            display_cmd = f"bazel {verb} {target}"

    print(f"\n$ {display_cmd}")
    print("─" * 60, flush=True)

    try:
        for c in display_cmd + '\n':
            fcntl.ioctl(sys.stdin, termios.TIOCSTI, c)
        sys.exit(0)
    except OSError:
        # Fallback if TIOCSTI is blocked by kernel settings
        os.execvp(exec_args[0], exec_args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
