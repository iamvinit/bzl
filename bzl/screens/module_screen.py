"""Module browser — Screen 1."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static
from textual.containers import Horizontal, Vertical
from textual import work

from .base_screen import BaseBzlScreen, BZL_LOGO
from ..widgets.fuzzy_list import FuzzyList


class ModuleScreen(BaseBzlScreen):
    """Screen 1: fuzzy-search Bazel modules."""

    BINDINGS = [
        *BaseBzlScreen.BINDINGS,
        Binding("escape", "quit_app", "Quit", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-bar"):
            yield Static(BZL_LOGO, id="logo")
            with Vertical(id="top-right"):
                yield Static("", id="header")
                yield Static("", id="shortcuts")
                yield Static("", id="breadcrumb")
        yield FuzzyList(
            items=list(self.app.targets.keys()),
            fmt_item=self._fmt_module,
            id="list",
        )
        yield Static("", id="filter-bar")

    def on_mount(self) -> None:
        self._filter = ""
        self._rebuild()

    def _fmt_module(self, module: str) -> str:
        count = len(self.app.targets.get(module, []))
        noun = "target" if count == 1 else "targets"
        pad = max(1, 48 - len(module))
        return f"{module}{' ' * pad}[dim]{count} {noun}[/dim]"

    def _refresh_breadcrumb(self) -> None:
        fl = self.query_one(FuzzyList)
        crumb = (
            f"[dim]Modules[/dim]  "
            f"[bold white]{fl.count}[/bold white][dim]/{fl.total_count}[/dim]"
        )
        self.query_one("#breadcrumb", Static).update(crumb)

    def _get_shortcuts(self) -> list[tuple[str, str]]:
        return [
            ("<enter>", "select"), ("<ctrl+v>", "toggle cmd"), ("<ctrl+e>", "clean"),
            ("<ctrl+x>", "expunge"), ("<ctrl+f>", "refresh"), ("<ctrl+k>", "config"),
            ("<esc>", "quit")
        ]

    def action_confirm(self) -> None:
        item = self.query_one(FuzzyList).selected_item
        if item:
            from .genrule_screen import GenruleScreen
            self.app.push_screen(GenruleScreen(module=item))

    def action_quit_app(self) -> None:
        self.app.exit(None)

    @work(exclusive=True, thread=True)
    def action_refresh_query(self) -> None:
        def set_loading(loading: bool) -> None:
            self.query_one(FuzzyList).loading = loading

        self.app.call_from_thread(set_loading, True)
        self.app.refresh_targets()

        def on_done() -> None:
            fl = self.query_one(FuzzyList)
            fl.update_items(list(self.app.targets.keys()))
            self._filter = ""
            fl.set_filter("")
            self._rebuild()
            fl.loading = False

        self.app.call_from_thread(on_done)

