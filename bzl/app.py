"""Textual App — wires screens together and holds shared state."""
from __future__ import annotations

from typing import Optional, Tuple, Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive

from .ssh import SSHConfig
from .screens.module_screen import ModuleScreen


class BzlApp(App):
    """Terminal UI for browsing and executing Bazel genrule targets."""

    CSS = """
Screen {
    background: #0a1628;
    color: #c8d8e8;
    layers: base;
}

#top-bar {
    height: auto;
    dock: top;
    background: #0a2540;
    border-bottom: solid #3d6896;
}

#logo {
    width: 50;
    padding: 0 1;
    content-align: center middle;
    color: #00d4ff;
    text-style: bold;
    border-right: solid #3d6896;
}

#top-right {
    width: 1fr;
    height: auto;
}

#header {
    height: 1;
    background: #0a2540;
    color: #00d4ff;
    padding: 0 2;
}

#breadcrumb {
    height: 1;
    background: #0d1f3c;
    color: #7b9abf;
    padding: 0 2;
}

#filter-bar {
    height: 1;
    background: #0f2035;
    color: white;
    padding: 0 2;
    dock: bottom;
}

FuzzyList {
    height: 1fr;
    background: #0a1628;
}

#shortcuts {
    height: auto;
    background: #0a1628;
    color: #ffffff;
    padding: 0 2;
}
"""

    # Shared reactive state
    verb: reactive[str] = reactive("build")
    kinds: reactive[list[str]] = reactive(["genrule"])

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+k", "toggle_kinds", "Kinds", show=True),
    ]

    def __init__(
        self,
        targets: dict[str, list[str]],
        ssh_config: Optional[SSHConfig],
        scope: str,
        kinds: list[str] = ["genrule"],
        on_kinds_change: Optional[Callable[[list[str]], None]] = None,
        cache_key: Optional[str] = None,
        cache_ttl_seconds: int = 1209600,  # 2 weeks
    ) -> None:
        super().__init__()
        self.targets = targets
        self.ssh_config = ssh_config
        self.scope = scope
        self._on_kinds_change = on_kinds_change
        self.kinds = kinds
        self._cache_key = cache_key
        self._cache_ttl = cache_ttl_seconds

    def watch_kinds(self, kinds: list[str]) -> None:
        """Persist kinds change when the reactive variable updates."""
        if self._on_kinds_change:
            self._on_kinds_change(kinds)

    def on_mount(self) -> None:
        self.push_screen(ModuleScreen())

    def action_quit_app(self) -> None:
        self.exit(None)

    def action_toggle_kinds(self) -> None:
        from .screens.kind_select_screen import KindSelectScreen
        self.push_screen(KindSelectScreen())

    def refresh_targets(self) -> None:
        """Bust cache, re-run bazel query, update self.targets in-place."""
        from .bazel import query_local, query_ssh, parse_query_output, bust_cache, save_cache
        bust_cache(self._cache_key, self.scope, self.kinds)
        try:
            if self.ssh_config:
                output = query_ssh(self.ssh_config, self.scope, self.kinds)
            else:
                output = query_local(self.scope, self.kinds)
            self.targets = parse_query_output(output)
            save_cache(self._cache_key, self.scope, self.kinds, self.targets)
        except Exception:
            pass  # keep old data on failure
