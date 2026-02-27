"""Genrule browser — Screen 2."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static
from textual.containers import Horizontal, Vertical
from textual import work

from .base_screen import BaseBzlScreen, BZL_LOGO
from ..widgets.fuzzy_list import FuzzyList


class GenruleScreen(BaseBzlScreen):
    """Screen 2: fuzzy-search genrules within a selected module."""

    BINDINGS = [
        *BaseBzlScreen.BINDINGS,
        Binding("escape", "go_back", "Back", priority=True),
    ]

    def __init__(self, module: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._module = module

    def compose(self) -> ComposeResult:
        rules = self.app.targets.get(self._module, [])
        with Horizontal(id="top-bar"):
            yield Static(BZL_LOGO, id="logo")
            with Vertical(id="top-right"):
                yield Static("", id="header")
                yield Static("", id="shortcuts")
                yield Static("", id="breadcrumb")
        yield FuzzyList(items=rules, id="list")
        yield Static("", id="filter-bar")

    def on_mount(self) -> None:
        self._rebuild()

    def _refresh_breadcrumb(self) -> None:
        fl = self.query_one(FuzzyList)
        self.query_one("#breadcrumb", Static).update(
            f"[dim]Modules[/dim] [dim]>[/dim] [bold cyan]{self._module}[/bold cyan]"
            f"  [bold white]{fl.count}[/bold white][dim]/{fl.total_count} targets[/dim]"
        )

    def _get_shortcuts(self) -> list[tuple[str, str]]:
        return [
            ("<enter>", "execute"), ("<ctrl+v>", "toggle cmd"), ("<ctrl+e>", "clean"),
            ("<ctrl+x>", "expunge"), ("<ctrl+f>", "refresh"), ("<ctrl+k>", "config"),
            ("<esc>", "back")
        ]

    def action_confirm(self) -> None:
        rule = self.query_one(FuzzyList).selected_item
        if rule:
            self.app.exit((f"{self._module}:{rule}", self.app.verb))

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @work(exclusive=True, thread=True)
    def action_refresh_query(self) -> None:
        def set_loading(loading: bool) -> None:
            self.query_one(FuzzyList).loading = loading

        self.app.call_from_thread(set_loading, True)
        self.app.refresh_targets()

        def on_done() -> None:
            rules = self.app.targets.get(self._module, [])
            fl = self.query_one(FuzzyList)
            fl.update_items(rules)
            self._filter = ""
            fl.set_filter("")
            self._rebuild()
            fl.loading = False

        self.app.call_from_thread(on_done)

