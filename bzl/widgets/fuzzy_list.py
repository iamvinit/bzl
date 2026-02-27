"""Reusable fuzzy-filtered list widget with virtual scrolling."""
from __future__ import annotations

from textual.widget import Widget
from textual.message import Message
from rich.text import Text


def fuzzy_filter(query: str, items: list[str]) -> list[str]:
    """Substring filter (case-insensitive). Supports multiple space-separated tokens."""
    if not query.strip():
        return items
    tokens = query.lower().split()
    return [item for item in items if all(t in item.lower() for t in tokens)]


class FuzzyList(Widget):
    """
    A scrollable list with built-in substring filtering and cursor.

    The parent Screen drives the state (filter, cursor) and calls
    set_filter() / move_up() / move_down(). The widget re-renders on
    every change via self.refresh().

    Emits:
        FuzzyList.Selected  — when a row is confirmed (caller must call confirm())
    """

    DEFAULT_CSS = """
    FuzzyList {
        height: 1fr;
        background: #0a1628;
        border: none;
        overflow: hidden;
    }
    """

    class Selected(Message):
        def __init__(self, item: str) -> None:
            super().__init__()
            self.item = item

    # ------------------------------------------------------------------ state

    def __init__(
        self,
        items: list[str],
        fmt_item=None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._all_items = items
        self._fmt = fmt_item or (lambda item: item)
        self._filter = ""
        self._cursor = 0
        self._filtered: list[str] = items[:]

    # ----------------------------------------------------------------- public

    def set_filter(self, query: str) -> None:
        self._filter = query
        self._filtered = fuzzy_filter(query, self._all_items)
        self._cursor = 0
        self.refresh()

    def move_up(self) -> None:
        if self._cursor > 0:
            self._cursor -= 1
            self.refresh()

    def move_down(self) -> None:
        if self._cursor < len(self._filtered) - 1:
            self._cursor += 1
            self.refresh()

    def confirm(self) -> None:
        """Call this when Enter is pressed — emits Selected."""
        if self._filtered:
            self.post_message(self.Selected(self._filtered[self._cursor]))

    def update_items(self, items: list[str]) -> None:
        self._all_items = items
        self._filtered = fuzzy_filter(self._filter, self._all_items)
        self._cursor = 0
        self.refresh()

    @property
    def selected_item(self) -> str | None:
        if self._filtered and 0 <= self._cursor < len(self._filtered):
            return self._filtered[self._cursor]
        return None

    @property
    def count(self) -> int:
        return len(self._filtered)

    @property
    def total_count(self) -> int:
        return len(self._all_items)

    # ----------------------------------------------------------------- render

    def render(self) -> Text:
        height = max(1, self.size.height)
        items = self._filtered

        if not items:
            t = Text()
            t.append("  (no matches)\n", style="dim italic")
            return t

        # Virtual scroll: keep cursor centred
        half = height // 2
        start = max(0, self._cursor - half)
        end = min(len(items), start + height)
        if end - start < height:
            start = max(0, end - height)

        t = Text()
        for i in range(start, end):
            item = items[i]
            label = self._fmt(item)
            if i == self._cursor:
                t.append(f" ▶ {label}\n", style="bold #00d4ff on #1a3a5c")
            else:
                t.append(f"   {label}\n", style="#c8d8e8")

        # Pad remaining rows
        for _ in range(height - (end - start)):
            t.append("\n")

        return t
