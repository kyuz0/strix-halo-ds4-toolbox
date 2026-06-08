from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Input, OptionList, Button, Label
from textual import on, events
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget


# ── Confirm / Select Modals ─────────────────────────────────────────────────

class ConfirmModal(ModalScreen[bool]):
    """A modal dialog that asks a Yes/No question."""
    def __init__(self, message: str, yes_text: str = "Yes", no_text: str = "No", id: str = None):
        super().__init__(id=id)
        self.message = message
        self.yes_text = yes_text
        self.no_text = no_text

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm_dialog"):
            yield Label(self.message, id="confirm_message")
            with Horizontal(id="confirm_buttons"):
                yield Button(self.yes_text, variant="error", id="btn_yes")
                yield Button(self.no_text, variant="primary", id="btn_no")

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_yes":
            self.dismiss(True)
        else:
            self.dismiss(False)


class SelectModal(ModalScreen[int]):
    """A modal dialog that asks the user to select an option."""
    def __init__(self, title: str, options: list[str], id: str = None):
        super().__init__(id=id)
        self.title = title
        self.options = options

    def compose(self) -> ComposeResult:
        with Vertical(id="select_dialog"):
            yield Label(self.title, id="select_title")
            yield OptionList(*self.options, id="select_list")
            with Horizontal(id="select_buttons"):
                yield Button("Cancel", variant="error", id="btn_cancel")

    @on(OptionList.OptionSelected, "#select_list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_index)

    @on(Button.Pressed, "#btn_cancel")
    def on_cancel(self, event: Button.Pressed) -> None:
        self.dismiss(None)


# ── Dropdown Overlay (screen-level floating list) ───────────────────────────

class _DropdownOverlay(Widget):
    """
    A free-floating dropdown mounted directly on the Screen's overlay layer.
    Positioned absolutely using screen-space coordinates.
    Navigation is driven externally via cursor_down/cursor_up/select_current.
    Mouse clicks on options fire the on_select callback immediately.
    """

    DEFAULT_CSS = """
    _DropdownOverlay {
        layer: overlay;
        background: #1e1e1e;
        border: solid #536DFE;
        height: auto;
        max-height: 12;
        width: 40;
    }
    _DropdownOverlay > OptionList {
        background: transparent;
        border: none;
        height: auto;
        max-height: 10;
        width: 1fr;
    }
    """

    def __init__(self, options: list[tuple[str, str]], on_select, x: int, y: int, width: int):
        super().__init__()
        self._options = list(options)
        self._on_select = on_select
        self._pos_x = x
        self._pos_y = y
        self._pos_width = width
        # Overlay must not steal focus
        self.can_focus = False

    def compose(self) -> ComposeResult:
        opt_list = OptionList(*[label for label, _ in self._options])
        opt_list.can_focus = False
        yield opt_list

    def on_mount(self) -> None:
        self.styles.offset = (self._pos_x, self._pos_y)
        self.styles.width = self._pos_width

    def update_options(self, options: list[tuple[str, str]]) -> None:
        self._options = list(options)
        opt_list = self.query_one(OptionList)
        opt_list.clear_options()
        for label, _ in self._options:
            opt_list.add_option(label)

    def cursor_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def cursor_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def select_current(self) -> None:
        """Select whichever item the OptionList cursor is on."""
        opt_list = self.query_one(OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._options):
            label, val = self._options[idx]
            self._on_select(val, label)

    @on(OptionList.OptionSelected)
    def _on_mouse_click_option(self, event: OptionList.OptionSelected) -> None:
        """Handle mouse clicks on options (fires even when can_focus=False)."""
        event.stop()
        label = str(event.option.prompt)
        val = label
        for l, v in self._options:
            if l == label:
                val = v
                break
        self._on_select(val, label)


# ── SearchableSelect ─────────────────────────────────────────────────────────

class SearchableSelect(Widget):
    """
    A filterable combobox widget.

    Behaviour:
    - Click or focus → shows all options in a floating overlay.
    - Type → filters the list in real time.
    - ↑/↓ → navigate list while keeping focus on Input.
    - Enter → confirm highlighted option.
    - Escape → close overlay without changing value.
    - Tab/blur → close overlay.

    Emits SearchableSelect.Changed when the selected value changes.
    Compatible with Select.Changed drop-in replacement pattern via `.value`.
    """

    DEFAULT_CSS = """
    SearchableSelect {
        height: 1;
        width: 1fr;
        background: #262626;
    }
    SearchableSelect > Input {
        border: none;
        height: 1;
        width: 1fr;
        background: transparent;
        padding: 0 1;
    }
    SearchableSelect:focus-within {
        background: #303030;
    }
    SearchableSelect > Input:focus {
        color: #e57373;
        text-style: bold;
    }
    """

    class Changed(Message):
        """Posted when the selected value changes."""
        def __init__(self, value: str, select: "SearchableSelect"):
            self.value = value
            self.select = select
            super().__init__()

        @property
        def control(self) -> "SearchableSelect":
            return self.select

    def __init__(self, prompt: str = "Search...", id: str = None):
        super().__init__(id=id)
        self.border_title = None
        self.prompt = prompt
        self._options: list[tuple[str, str]] = []
        self._current_value: str = ""
        self._overlay: _DropdownOverlay | None = None
        self._suppress_change: bool = False

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self.prompt)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_options(self, options: list) -> None:
        """Set options as (label, value) tuples or plain strings."""
        self._options = []
        for opt in options:
            if isinstance(opt, tuple):
                self._options.append((str(opt[0]), str(opt[1])))
            else:
                self._options.append((str(opt), str(opt)))
        if self._overlay and self._overlay.is_attached:
            self._overlay.update_options(self._options)

    @property
    def value(self) -> str:
        return self._current_value

    @value.setter
    def value(self, new_value: str) -> None:
        self._current_value = new_value
        label = new_value
        for l, v in self._options:
            if v == new_value:
                label = l
                break
        inp = self.query_one(Input)
        with inp.prevent(Input.Changed):
            inp.value = label
        self.post_message(self.Changed(new_value, self))

    def focus_input(self) -> None:
        self.query_one(Input).focus()

    # ── Overlay lifecycle ───────────────────────────────────────────────────

    def _get_filtered(self, term: str = "") -> list[tuple[str, str]]:
        if not term:
            return self._options
        t = term.lower()
        return [(l, v) for l, v in self._options if t in l.lower() or t in v.lower()]

    def _open_overlay(self, filter_term: str = "") -> None:
        if self._overlay and self._overlay.is_attached:
            return
        if not self._options:
            return
        filtered = self._get_filtered(filter_term) or self._options
        inp = self.query_one(Input)
        try:
            region = inp.screen_region
        except Exception:
            region = inp.region
        overlay = _DropdownOverlay(
            options=filtered,
            on_select=self._on_option_selected,
            x=region.x,
            y=region.y + region.height,
            width=region.width,
        )
        self._overlay = overlay
        self.app.screen.mount(overlay)

    def _close_overlay(self) -> None:
        if self._overlay and self._overlay.is_attached:
            self._overlay.remove()
        self._overlay = None

    def _on_option_selected(self, value: str, label: str) -> None:
        """Called by the overlay when user selects an option (keyboard or mouse)."""
        self._current_value = value
        inp = self.query_one(Input)
        with inp.prevent(Input.Changed):
            inp.value = label
        self._close_overlay()
        self.post_message(self.Changed(value, self))

    # ── Event handlers ──────────────────────────────────────────────────────

    @on(Input.Changed)
    def _on_input_changed(self, event: Input.Changed) -> None:
        if self._suppress_change:
            self._suppress_change = False
            return
        term = event.value.lower()
        if self._overlay and self._overlay.is_attached:
            filtered = self._get_filtered(term) or self._options
            self._overlay.update_options(filtered)
        else:
            # Open overlay as soon as user starts typing
            self._open_overlay(term)
        if not event.value:
            self._current_value = ""
            self.post_message(self.Changed("", self))

    @on(events.Click)
    def _on_widget_clicked(self, event: events.Click) -> None:
        """Open the full dropdown when clicking the widget."""
        inp = self.query_one(Input)
        self._open_overlay(inp.value.lower())
        inp.focus()

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard navigation while overlay is open."""
        if event.key in ("down", "up") and not (self._overlay and self._overlay.is_attached):
            # ↓/↑ with no overlay → open it
            self._open_overlay(self.query_one(Input).value.lower())
            event.prevent_default()
            event.stop()
            return

        if not (self._overlay and self._overlay.is_attached):
            return

        if event.key == "down":
            event.prevent_default()
            event.stop()
            self._overlay.cursor_down()
        elif event.key == "up":
            event.prevent_default()
            event.stop()
            self._overlay.cursor_up()
        elif event.key == "enter":
            event.prevent_default()
            event.stop()
            self._overlay.select_current()
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            self._close_overlay()

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        """Close overlay when the Input loses focus (tab / click elsewhere)."""
        # Small delay so a mouse-click on the overlay fires its OptionSelected first
        self.set_timer(0.15, self._close_overlay)
