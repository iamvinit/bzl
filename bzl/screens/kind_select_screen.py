"""Kind selection screen — allows toggling rule types."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import SelectionList, Static, Footer, Header
from textual.containers import Vertical
from textual.widgets.selection_list import Selection

class KindSelectScreen(ModalScreen):
    """A modal screen that lets users select which rule kinds to query."""

    CSS = """
    KindSelectScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }

    #dialog {
        width: 65;
        height: 25;
        background: #0f2035;
        border: thick #00d4ff;
        padding: 1 2;
        layout: vertical;
    }

    #title {
        content-align: center middle;
        text-style: bold;
        color: #00d4ff;
        margin-bottom: 1;
    }

    #help-text {
        width: 100%;
        content-align: center middle;
        text-align: center;
        color: white;
        margin-bottom: 1;
    }

    #loading-msg {
        content-align: center middle;
        color: #7b9abf;
        margin-top: 2;
    }

    SelectionList {
        height: 1fr;
        border: none;
        background: #0a1628;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "Apply", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Select Rule Kinds", id="title")
            yield Static(
                "[dim]<space>[/dim] toggle selection • "
                "[dim]<enter>[/dim] apply • "
                "[dim]<esc>[/dim] cancel",
                id="help-text"
            )
            yield Static("Refreshing bazel filters...", id="loading-msg")
            yield SelectionList(id="kind-list")

    def on_mount(self) -> None:
        self.query_one("#kind-list").display = False
        self.run_worker(self._fetch_kinds, thread=True)

    def _fetch_kinds(self) -> None:
        """Fetch all unique rule types from Bazel."""
        from ..bazel import query_all_kinds_local, query_all_kinds_ssh
        
        try:
            if self.app.ssh_config:
                all_kinds = query_all_kinds_ssh(self.app.ssh_config, self.app.scope)
            else:
                all_kinds = query_all_kinds_local(self.app.scope)
            
            # Combine with currently selected kinds just in case
            all_kinds = sorted(list(set(all_kinds) | set(self.app.kinds)))
            
            self.app.call_from_thread(self._populate_list, all_kinds)
        except Exception:
            self.app.call_from_thread(self._populate_list, self.app.kinds)

    def _populate_list(self, all_kinds: list[str]) -> None:
        """Update the UI with the fetched kinds."""
        sl = self.query_one(SelectionList)
        for kind in all_kinds:
            sl.add_option(Selection(kind, kind, kind in self.app.kinds))
        
        self.query_one("#loading-msg").display = False
        sl.display = True
        sl.focus()

    def action_cancel(self) -> None:
        self.dismiss()

    def action_submit(self) -> None:
        selected_kinds = self.query_one(SelectionList).selected
        if not selected_kinds:
            # Don't allow empty selection, default to genrule
            selected_kinds = ["genrule"]
        
        if set(selected_kinds) != set(self.app.kinds):
            self.app.kinds = selected_kinds
            self.app.refresh_targets()
            # If we are on ModuleScreen, we refresh its list.
            if hasattr(self.app.screen, "action_refresh_query"):
                self.app.screen.action_refresh_query()
        
        self.dismiss()
