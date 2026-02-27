"""SSH config and command builder."""
from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SSHConfig:
    """Holds SSH connection details and builds exec/query commands."""

    host: str          # e.g. "user@build-host"
    remote_dir: str    # e.g. "/home/user/my-repo"

    @classmethod
    def from_args(cls, host: str, remote_dir: Optional[str]) -> "SSHConfig":
        return cls(
            host=host,
            remote_dir=remote_dir or os.getcwd(),
        )

    def build_exec_args(self, target: Optional[str] = None, verb: str = "build") -> list[str]:
        """Returns argv for os.execvp — ssh -t host 'cd dir && bazel verb [target]'."""
        target_str = f" {target}" if target else ""
        remote_cmd = f"cd {shlex.quote(self.remote_dir)} && bazel {verb}{target_str}"
        return ["ssh", "-t", self.host, remote_cmd]

    def build_all_kinds_query_cmd(self, scope: str) -> list[str]:
        """Returns argv for subprocess — ssh host 'cd dir && bazel query ...'."""
        remote_cmd = (
            f"cd {shlex.quote(self.remote_dir)} && "
            f"bazel query '{scope}' --output label_kind"
        )
        return ["ssh", self.host, remote_cmd]

    def build_query_cmd(self, scope: str, kinds: list[str]) -> list[str]:
        """Returns argv for subprocess — ssh host 'cd dir && bazel query ...'."""
        kind_expr = "|".join(kinds) if len(kinds) > 1 else kinds[0]
        remote_cmd = (
            f"cd {shlex.quote(self.remote_dir)} && "
            f"bazel query \"kind('{kind_expr}', {scope})\""
        )
        return ["ssh", self.host, remote_cmd]

    def label(self) -> str:
        return f"🌐 SSH: {self.host}"
