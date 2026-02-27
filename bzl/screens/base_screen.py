from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Horizontal, Vertical
from textual import work
import pyfiglet

try:
    BZL_LOGO = pyfiglet.figlet_format("bzl", font="slant_relief")
except Exception:
    BZL_LOGO = "bzl"

from ..widgets.fuzzy_list import FuzzyList


class BaseBzlScreen(Screen):
    """Base class containing shared layout and logic for Bzl screens."""

    BINDINGS = [
        Binding("ctrl+v", "toggle_verb", "Toggle Cmd", priority=True),
        Binding("ctrl+e", "clean", "Clean", show=False, priority=True),
        Binding("ctrl+x", "clean_expunge", "Clean Expunge", show=False, priority=True),
        Binding("ctrl+f", "refresh_query", "Refresh", priority=True),
        Binding("up", "cursor_up", "Up", show=False, priority=True),
        Binding("down", "cursor_down", "Down", show=False, priority=True),
        Binding("enter", "confirm", "Select", show=False, priority=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._filter = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-bar"):
            yield Static(BZL_LOGO, id="logo")
            with Vertical(id="top-right"):
                yield Static("", id="header")
                yield Static("", id="shortcuts")
                yield Static("", id="breadcrumb")
        yield FuzzyList(
            items=[],
            id="list",
        )
        yield Static("", id="filter-bar")

    def _rebuild(self) -> None:
        self._refresh_header()
        self._refresh_shortcuts()
        self._refresh_breadcrumb()
        self._refresh_filter()

    def _refresh_header(self) -> None:
        verb = self.app.verb.upper()
        if self.app.verb == "build":
            verb_style = "bold white on green"
        elif self.app.verb == "test":
            verb_style = "bold white on magenta"
        else:
            verb_style = "bold white on deep_sky_blue1"

        if self.app.ssh_config:
            ctx = f"[bold white on dark_orange] {self.app.ssh_config.label()} [/]"
        else:
            ctx = f"[bold white on cyan] {self.app.scope} [/]"

        self.query_one("#header", Static).update(
            f" {ctx} [{verb_style}] {verb} [/] "
        )

    def _refresh_breadcrumb(self) -> None:
        # Override in subclasses
        pass

    def _refresh_filter(self) -> None:
        self.query_one("#filter-bar", Static).update(
            f"[dim]Filter:[/dim] [bold white]>[/bold white] {self._filter}[blink]█[/blink]"
        )

    def _get_shortcuts(self) -> list[tuple[str, str]]:
        return [
            ("<enter>", "select"), ("<ctrl+v>", "toggle cmd"), ("<ctrl+e>", "clean"),
            ("<ctrl+x>", "expunge"), ("<ctrl+f>", "refresh"), ("<ctrl+k>", "config"),
            ("<esc>", "back")
        ]

    def _refresh_shortcuts(self) -> None:
        logo_lines = len(BZL_LOGO.splitlines())
        available_lines = max(1, logo_lines - 2)  # Header and breadcrumb take 2 lines

        shortcuts = self._get_shortcuts()

        rows = [""] * available_lines
        for i, (k, v) in enumerate(shortcuts):
            row_idx = i % available_lines
            part = f"[dim]{k:<10}[/] {v:<15}"
            rows[row_idx] += part

        self.query_one("#shortcuts", Static).update("\n".join(r.rstrip() for r in rows if r.strip()))

    def on_key(self, event) -> None:
        if event.key == "backspace":
            self._filter = self._filter[:-1]
            self.query_one(FuzzyList).set_filter(self._filter)
            self._refresh_filter()
            self._refresh_breadcrumb()
            event.stop()
        elif event.character and event.character.isprintable():
            self._filter += event.character
            self.query_one(FuzzyList).set_filter(self._filter)
            self._refresh_filter()
            self._refresh_breadcrumb()
            event.stop()

    def action_cursor_up(self) -> None:
        self.query_one(FuzzyList).move_up()

    def action_cursor_down(self) -> None:
        self.query_one(FuzzyList).move_down()

    def action_toggle_verb(self) -> None:
        verbs = ["build", "run", "test"]
        try:
            nxt = verbs.index(self.app.verb) + 1
        except ValueError:
            nxt = 0
        self.app.verb = verbs[nxt % len(verbs)]
        self._refresh_header()
        self._refresh_shortcuts()

    def action_clean(self) -> None:
        self.app.exit((None, "clean"))
        
    def action_clean_expunge(self) -> None:
        self.app.exit((None, "clean --expunge"))

