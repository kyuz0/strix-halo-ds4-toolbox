from textual.app import App, ComposeResult
from textual.theme import Theme
from textual import on, events, work
from textual.widgets import Header, Footer, TabbedContent, TabPane, Button, Static, Label, Input, DataTable, Collapsible
from textual.containers import Vertical, Horizontal, VerticalScroll
import os
import subprocess

from src.toolbox_manager import get_all_toolboxes, detect_engines, get_os_toolbox_cmd, get_remote_image_date, create_toolbox, delete_toolbox
from src.model_manager import scan_local_models, get_download_cmd, get_models_dir, save_models_dir, is_model_downloaded
from src.server_runner import build_server_cmd
from src.config import load_models
from src.widgets import ConfirmModal, SelectModal, SearchableSelect
import pyfiglet

import importlib.metadata

def generate_banner() -> str:
    ascii_art = pyfiglet.figlet_format("ds4 Strix Halo Cockpit", font="slant")
    try:
        version = importlib.metadata.version("ds4-cockpit")
        version_str = f"v{version}"
    except Exception:
        version_str = "v?.?.?"
        
    return f"[bold #8C9EFF]{ascii_art}[/][dim]{version_str}[/dim]"

class Ds4CockpitApp(App):
    TITLE = "ds4 Strix Halo Cockpit"
    CSS = """
    DataTable > .datatable--cursor { background: #333333; color: auto; text-style: none; }
    DataTable.inactive-table > .datatable--cursor { background: transparent; text-style: none; }
    DataTable > .datatable--header { background: #2a2a2a; }
    OptionList > .option-list--option-highlighted { background: transparent; color: #8C9EFF; text-style: bold; }
    
    Header { background: #536DFE; }
    Tab, Tab:hover, Tab:focus, Tab.-active { background: transparent !important; }
    Tab:focus { color: #8C9EFF !important; text-style: bold; }
    Underline > .underline--active { background: #536DFE !important; }
    Tabs .underline--active { background: #536DFE !important; }
    Tabs:focus .underline--active { background: #536DFE !important; }
    Tab.-active { color: #8C9EFF !important; }
    
    .inline-row { height: auto; max-height: 5; margin-top: 1; }
    .inline-row .inline-label { width: auto; min-width: 12; text-style: bold; color: #8C9EFF; padding-right: 1; height: 1; content-align: left middle; }
    .inline-row SearchableSelect { width: 1fr; }
    .inline-row Input { width: 1fr; }
    .short-field { width: 1fr; height: auto; max-height: 3; margin-right: 2; }
    .short-field .inline-label { width: auto; min-width: 8; height: 1; }
    
    #banner { text-align: center; margin-bottom: 0; height: auto; text-style: bold; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 2; }
    .box { padding: 1 2; margin-bottom: 1; background: $surface; border: round #536DFE; color: $text; text-style: bold; text-align: center; height: auto; }
    #btn_row { margin-top: 1; height: auto; align: left middle; }
    Button { margin-right: 1; height: 1; border: none; min-width: 12; }
    
    .btn-toggle-all { height: auto; min-width: 10; margin: 1 0; border: none; background: #333333; }
    .btn-toggle-all:hover { background: #536DFE; }
    
    #toolbox_container { height: 1fr; }
    #toolbox_container DataTable { height: auto; border: none; margin-bottom: 1; }
    #toolbox_container Vertical { height: auto; }
    
    #local_model_list { border: none; height: 1fr; }
    #model_manager_view { height: 1fr; padding: 0; }
    .model-zone { background: #1e1e1e; border: round #333333; padding: 0 1; margin-bottom: 1; height: auto; }
    .model-zone:focus-within { border: round #536DFE; }
    #download_zone { height: auto; }
    #local_zone { height: 1fr; }
    .zone-title { color: #8C9EFF; text-style: bold; background: transparent; width: 100%; margin-bottom: 0; margin-top: 0; height: auto; }
    
    Input { margin: 0; height: 1; border: none; }
    ConfirmModal, SelectModal { align: center middle; background: rgba(0, 0, 0, 0.7); }
    #confirm_dialog { width: 90%; max-width: 100; height: auto; border: solid #536DFE; background: #1e1e1e; padding: 1 2; }
    #select_dialog { width: 90%; max-width: 100; height: 80%; border: solid #536DFE; background: #1e1e1e; padding: 1 2; }
    #confirm_message, #select_title { text-align: center; text-style: bold; color: #8C9EFF; margin-bottom: 1; width: 100%; }
    #confirm_buttons, #select_buttons { align: center middle; height: auto; }
    #select_list { border: solid #536DFE; height: 1fr; min-height: 10; margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(generate_banner(), id="banner")
        
        with TabbedContent(initial="tab-toolboxes"):
            with TabPane("Interactive Toolboxes", id="tab-toolboxes"):
                yield Vertical(
                    Static("Manage and enter ds4 toolbox containers.", classes="box"),
                    VerticalScroll(id="toolbox_container"),
                    Horizontal(
                        Button("Enter", id="btn_enter", variant="success"),
                        Button("Create/Update", id="btn_create_update", variant="warning"),
                        Button("Delete", id="btn_delete", variant="error"),
                        Button("Check Updates", id="btn_check_updates"),
                        Button("Refresh", id="btn_refresh"),
                        id="btn_row"
                    )
                )
            with TabPane("Server Mode", id="tab-server"):
                yield VerticalScroll(
                    Static("Launch ds4-server directly without entering an interactive environment.", classes="box"),
                    Horizontal(
                        Label("Engine", classes="inline-label"),
                        SearchableSelect(prompt="Select Container Engine", id="sel_engine"),
                        classes="inline-row"
                    ),
                    Horizontal(
                        Label("Image", classes="inline-label"),
                        SearchableSelect(prompt="Select Toolbox Image", id="sel_image"),
                        classes="inline-row"
                    ),
                    Horizontal(
                        Label("Model", classes="inline-label"),
                        SearchableSelect(prompt="Select Local Model", id="sel_model"),
                        classes="inline-row"
                    ),
                    Horizontal(
                        Horizontal(Label("Context", classes="inline-label"), Input(placeholder="126000", id="inp_ctx", value="126000"), classes="short-field"),
                        Horizontal(Label("Host", classes="inline-label"), Input(placeholder="localhost", id="inp_host", value="localhost"), classes="short-field"),
                        Horizontal(Label("Port", classes="inline-label"), Input(placeholder="8000", id="inp_port", value="8000"), classes="short-field"),
                        classes="inline-row"
                    ),
                    Horizontal(
                        Horizontal(Label("KV Disk Dir", classes="inline-label"), Input(placeholder="/tmp/ds4-kv", id="inp_kv_dir", value="/tmp/ds4-kv"), classes="short-field"),
                        Horizontal(Label("KV Disk MB", classes="inline-label"), Input(placeholder="8192", id="inp_kv_mb", value="8192"), classes="short-field"),
                        classes="inline-row"
                    ),
                    Horizontal(
                        Label("MTP Model", classes="inline-label"),
                        SearchableSelect(prompt="Select MTP Model (Optional)", id="sel_mtp_model"),
                        classes="inline-row"
                    ),
                    Horizontal(
                        Horizontal(Label("Role", classes="inline-label"), SearchableSelect(prompt="Standalone", id="sel_role"), classes="short-field"),
                        Horizontal(Label("Layers", classes="inline-label"), Input(placeholder="e.g. 0:21", id="inp_layers", value=""), classes="short-field"),
                        Horizontal(Label("Address", classes="inline-label"), Input(placeholder="IP Port", id="inp_peer_addr", value=""), classes="short-field"),
                        classes="inline-row"
                    ),
                    Horizontal(
                        Label("Extra Args", classes="inline-label"),
                        Input(placeholder="e.g. --mtp-draft 1", id="inp_custom_args", value=""),
                        classes="inline-row"
                    ),
                    Horizontal(
                        Button("Start ds4-server", id="btn_start_server", variant="primary"),
                        id="btn_row"
                    )
                )
            with TabPane("Model Manager", id="tab-models"):
                with Vertical(id="model_manager_view"):
                    with Vertical(id="download_zone", classes="model-zone"):
                        yield Label("📥 Curated DeepSeek V4 Downloader", classes="zone-title")
                        with Horizontal(classes="inline-row"):
                            yield Label("Model", classes="inline-label")
                            yield SearchableSelect(prompt="Select DeepSeek V4 model...", id="sel_download_model")
                            yield Button("Download", id="btn_download", variant="success")
                    
                    with Vertical(id="local_zone", classes="model-zone"):
                        yield Label("📂 Local GGUF Directory", classes="zone-title")
                        with Horizontal(classes="inline-row"):
                            yield Label("Storage Path", classes="inline-label")
                            yield Input(placeholder="e.g. ~/ds4", id="inp_models_dir", value=str(get_models_dir()))
                            yield Button("Save Path", id="btn_save_models_path")
                            yield Button("Scan Local", id="btn_scan_models", variant="primary")
                        
                        yield DataTable(id="local_model_list", cursor_type="row")
        yield Footer()

    def on_mount(self):
        cockpit_theme = Theme(
            name="deepseek-purple",
            primary="#536DFE",
            secondary="#304FFE",
            accent="#8C9EFF",
            foreground="#ffffff",
            background="#121212",
            surface="#1e1e1e",
            panel="#2a2a2a",
            warning="#fbc02d",
            error="#d32f2f",
            success="#4caf50",
            dark=True,
        )
        self.register_theme(cockpit_theme)
        self.theme = "deepseek-purple"
        
        self.selected_toolboxes = set()
        self.refresh_toolboxes()
        self.refresh_models()
        
        engines = detect_engines()
        sel_engine = self.query_one("#sel_engine", SearchableSelect)
        sel_engine.set_options([(e, e) for e in engines])
        if engines:
            sel_engine.value = engines[0]

        curated_cfg = load_models()
        self.download_repo = curated_cfg.get("repo", "antirez/deepseek-v4-gguf")
        
        sel_dl = self.query_one("#sel_download_model", SearchableSelect)
        opts = []
        for m in curated_cfg.get("models", []):
            rec = "⭐ " if m.get("recommended") else ""
            opts.append((f"{rec}{m['name']} ({m['size_gb']}GB)", m["filename"]))
        sel_dl.set_options(opts)

        sel_role = self.query_one("#sel_role", SearchableSelect)
        sel_role.set_options([("Standalone", "Standalone"), ("Coordinator", "Coordinator"), ("Worker", "Worker")])
        sel_role.value = "Standalone"

    def refresh_toolboxes(self):
        self._mounting_tables = True
        grouped_data = get_all_toolboxes()
        self.toolboxes_dict = {}
        
        container = self.query_one("#toolbox_container", VerticalScroll)
        container.remove_children()
        
        for group_name, toolboxes in grouped_data.items():
            if not toolboxes: continue
            collapsed = group_name != "Official Toolboxes"
            table = DataTable(id=f"dt_{group_name.replace(' ', '_').replace('/', '')}", cursor_type="row")
            table.add_class("inactive-table")
            table.add_columns("Sel", "Toolbox Name", "Description", "Status", "Created", "Latest Release")
            
            for tb in toolboxes:
                self.toolboxes_dict[tb["name"]] = tb
                if tb["status"] == "Not Installed":
                    status_fmt = "[red]Needs Download[/red]"
                else:
                    status_fmt = "[green]Running[/green]" if "Up" in tb.get("status", "") else "[dim]Downloaded[/dim]"
                
                sel_fmt = "\\[x]" if tb['name'] in getattr(self, 'selected_toolboxes', set()) else "\\[ ]"
                table.add_row(sel_fmt, tb['name'], tb.get('description', ''), status_fmt, tb.get('created', ''), "")
                
            btn_toggle = Button("Select/Deselect All", id=f"btn_toggle_{table.id}", classes="btn-toggle-all")
            col = Collapsible(Vertical(btn_toggle, table), title=f"{group_name} ({len(toolboxes)})", collapsed=collapsed)
            container.mount(col)
            
        def finish_mounting():
            first = True
            for dt in self.query(DataTable):
                if dt.id and dt.id.startswith("dt_"):
                    if first and dt.row_count > 0:
                        dt.remove_class("inactive-table")
                        first = False
                    else:
                        dt.add_class("inactive-table")
            self._mounting_tables = False
            
        self.call_next(finish_mounting)
        self.refresh_server_images()

    def refresh_server_images(self):
        if not hasattr(self, 'toolboxes_dict'): return
        
        images = set()
        for tb in self.toolboxes_dict.values():
            images.add(tb["image"])
                    
        sel_image = self.query_one("#sel_image", SearchableSelect)
        sorted_images = sorted(list(images), key=lambda x: (1 if "multi-node" in x else 0, x))
        sel_image.set_options([(img, img) for img in sorted_images])
        if sorted_images:
            sel_image.value = sorted_images[0]



    def refresh_models(self):
        models = scan_local_models()
        self.current_models = models
        dt = self.query_one("#local_model_list", DataTable)
        dt.clear(columns=True)
        dt.add_columns("Filename")
        
        sel_model = self.query_one("#sel_model", SearchableSelect)
        sel_mtp = self.query_one("#sel_mtp_model", SearchableSelect)
        model_opts = []
        mtp_opts = [("None", "")]
        
        for m in models:
            dt.add_row(m["name"])
            model_opts.append((m["name"], m["path"]))
            if "mtp" in m["name"].lower():
                mtp_opts.append((m["name"], m["path"]))
            
        sel_model.set_options(model_opts)
        if model_opts:
            sel_model.value = model_opts[0][1]
            
        sel_mtp.set_options(mtp_opts)
        sel_mtp.value = ""

    def _toggle_row_selection(self, dt: DataTable, cursor_row: int):
        try:
            name = dt.get_cell_at((cursor_row, 1))
            if name in self.selected_toolboxes:
                self.selected_toolboxes.remove(name)
                dt.update_cell_at((cursor_row, 0), "\\[ ]")
            else:
                self.selected_toolboxes.add(name)
                dt.update_cell_at((cursor_row, 0), "\\[x]")
        except Exception:
            pass

    @on(SearchableSelect.Changed, "#sel_role")
    def on_role_changed(self, event: SearchableSelect.Changed) -> None:
        role = event.value
        inp_ctx = self.query_one("#inp_ctx", Input)
        inp_layers = self.query_one("#inp_layers", Input)
        inp_peer = self.query_one("#inp_peer_addr", Input)
        
        if role == "Coordinator":
            inp_ctx.value = "262144"
            inp_layers.value = "0:21"
            inp_peer.placeholder = "Listen IP Port (e.g. 0.0.0.0 8081)"
        elif role == "Worker":
            inp_ctx.value = "262144"
            inp_layers.value = "22:output"
            inp_peer.placeholder = "Coord IP Port (e.g. 192.168.1.1 8081)"
        else:
            inp_ctx.value = "126000"
            inp_layers.value = ""
            inp_peer.placeholder = "IP Port"
            
    @on(SearchableSelect.Changed, "#sel_mtp_model")
    def on_mtp_changed(self, event: SearchableSelect.Changed) -> None:
        custom_args = self.query_one("#inp_custom_args", Input)
        args_list = custom_args.value.split()
        if event.value and event.value != "None":
            if "--mtp-draft" not in args_list:
                args_list.extend(["--mtp-draft", "1"])
        else:
            if "--mtp-draft" in args_list:
                idx = args_list.index("--mtp-draft")
                # Remove --mtp-draft and its value if it exists
                if idx + 1 < len(args_list) and not args_list[idx+1].startswith("-"):
                    del args_list[idx:idx+2]
                else:
                    del args_list[idx]
        custom_args.value = " ".join(args_list)

    @on(events.MouseUp)
    def on_mouse_up(self, event: events.MouseUp):
        if isinstance(event.control, DataTable) and event.control.id and event.control.id.startswith("dt_"):
            import time
            self._last_dt_click_time = time.time()

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected):
        if event.control.id and event.control.id.startswith("dt_"):
            self._toggle_row_selection(event.control, event.cursor_row)

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted):
        if getattr(self, "_mounting_tables", False):
            return
            
        if event.control.id and event.control.id.startswith("dt_"):
            import time
            if time.time() - getattr(self, "_last_dt_click_time", 0.0) < 0.1:
                self._toggle_row_selection(event.control, event.cursor_row)
                
            try:
                for dt in self.query(DataTable):
                    if dt.id and dt.id.startswith("dt_"):
                        if dt == event.control:
                            dt.remove_class("inactive-table")
                        else:
                            dt.add_class("inactive-table")
            except Exception:
                pass

    def on_descendant_focus(self, event: events.DescendantFocus):
        widget = event.widget
        if isinstance(widget, DataTable) and widget.id and widget.id.startswith("dt_"):
            for dt in self.query(DataTable):
                if dt.id and dt.id.startswith("dt_"):
                    if dt == widget:
                        dt.remove_class("inactive-table")
                    else:
                        dt.add_class("inactive-table")

    def get_selected_toolboxes(self):
        tb_dict = getattr(self, 'toolboxes_dict', {})
        selected = []
        if getattr(self, 'selected_toolboxes', set()):
            for name in self.selected_toolboxes:
                if name in tb_dict:
                    selected.append(tb_dict[name])
        return selected

    def get_selected_toolbox(self):
        tb_dict = getattr(self, 'toolboxes_dict', {})
        if getattr(self, 'selected_toolboxes', set()) and len(self.selected_toolboxes) == 1:
            return tb_dict.get(list(self.selected_toolboxes)[0])
        return None

    def on_button_pressed(self, event: Button.Pressed):
        handlers = {
            "btn_refresh": self._handle_refresh,
            "btn_scan_models": self._handle_scan_models,
            "btn_check_updates": self._handle_check_updates,
            "btn_delete": self._handle_delete,
            "btn_create_update": self._handle_create_update,
            "btn_enter": self._handle_enter_toolbox,
            "btn_start_server": self._handle_start_server,
            "btn_save_models_path": self._handle_save_models_path,
            "btn_download": self._handle_download,
        }

        btn_id = event.button.id
        if btn_id in handlers:
            handlers[btn_id]()
        elif btn_id and btn_id.startswith("btn_toggle_dt_"):
            self._handle_toggle_select_all(btn_id)

    def _handle_refresh(self):
        self.refresh_toolboxes()
        self.notify("Toolbox list refreshed.", timeout=3)

    def _handle_check_updates(self):
        tbs = self.get_selected_toolboxes()
        if not tbs:
            self.notify("No toolboxes selected.", severity="warning")
            return
        self.notify(f"Checking updates for {len(tbs)} toolbox(es)...", timeout=3)
        self._check_updates_bg(tbs)

    @work(thread=True, exclusive=True)
    def _check_updates_bg(self, tbs: list):
        for tb in tbs:
            remote_date = get_remote_image_date(tb['image'])
            if remote_date:
                remote_date_str = remote_date[:10]
                self.app.call_from_thread(self._update_toolbox_cell, tb['name'], 5, remote_date_str)
                created_date = self._get_toolbox_cell(tb['name'], 4)
                if created_date and remote_date_str > created_date:
                    self.app.call_from_thread(self._update_toolbox_cell, tb['name'], 3, "[yellow]Needs Update[/yellow]")
        self.app.call_from_thread(self.notify, "Update check complete.", timeout=3)

    def _handle_delete(self):
        tbs = self.get_selected_toolboxes()
        tbs = [tb for tb in tbs if tb["status"] != "Not Installed"]
        if not tbs:
            self.notify("No installed toolboxes selected.", severity="warning")
            return
        names = ", ".join([tb['name'] for tb in tbs])
        self._pending_delete_tbs = tbs
        self.app.push_screen(
            ConfirmModal(f"Are you sure you want to delete: {names}?"),
            self._on_delete_confirmed
        )

    def _handle_create_update(self):
        tbs = self.get_selected_toolboxes()
        if not tbs:
            self.notify("No toolboxes selected.", severity="warning")
            return
        to_create, to_update, already_updated = [], [], []

        with self.suspend():
            print("\nChecking latest image versions from registry...")
        for tb in tbs:
            if tb["status"] == "Not Installed":
                to_create.append(tb)
            else:
                remote_date = get_remote_image_date(tb['image'])
                if remote_date:
                    remote_date_str = remote_date[:10]
                    if tb.get('created') and remote_date_str > tb.get('created', ''):
                        to_update.append(tb)
                    else:
                        already_updated.append(tb)
                else:
                    already_updated.append(tb)

        if already_updated:
            with self.suspend():
                print("\nThe following toolboxes are already up-to-date:")
                for tb in already_updated:
                    print(f"  - {tb['name']}")

        if not to_create and not to_update:
            with self.suspend():
                input("\nNothing to do. Press Enter to return to UI...")
            self.selected_toolboxes.clear()
            self.refresh_toolboxes()
            return

        if to_update:
            names = ", ".join([tb['name'] for tb in to_update])
            warning_msg = (
                f"The following toolboxes have updates available and will be DELETED and RECREATED:\n"
                f"  {names}\n\n"
                f"Any manually installed packages inside them will be lost. Continue?"
            )
            self._pending_update_tbs = to_update
            self._pending_create_tbs = to_create
            self.app.push_screen(ConfirmModal(warning_msg), self._on_update_confirmed)
        else:
            self._do_create_toolboxes(to_create)

    def _handle_enter_toolbox(self):
        tb = self.get_selected_toolbox()
        if not tb:
            self.notify("Select exactly one toolbox to enter.", severity="warning")
            return
        if tb["status"] == "Not Installed":
            self.notify("Cannot enter a toolbox that is not installed.", severity="warning")
            return
        cmd = get_os_toolbox_cmd()
        with self.suspend():
            os.system(f"{cmd} enter {tb['name']}")

    def _handle_start_server(self):
        engine = self.query_one("#sel_engine", SearchableSelect).value
        image = self.query_one("#sel_image", SearchableSelect).value
        model_path = self.query_one("#sel_model", SearchableSelect).value
        ctx = self.query_one("#inp_ctx", Input).value
        host = self.query_one("#inp_host", Input).value
        port = self.query_one("#inp_port", Input).value
        kv_dir = self.query_one("#inp_kv_dir", Input).value
        kv_mb = self.query_one("#inp_kv_mb", Input).value
        mtp_model = self.query_one("#sel_mtp_model", SearchableSelect).value
        role = self.query_one("#sel_role", SearchableSelect).value
        layers = self.query_one("#inp_layers", Input).value
        peer_addr = self.query_one("#inp_peer_addr", Input).value
        custom_args = self.query_one("#inp_custom_args", Input).value

        if engine and image and model_path and ctx.isdigit():
            kv_mb_val = int(kv_mb) if kv_mb.isdigit() else 8192
            
            tb_config = {}
            if hasattr(self, "toolboxes_dict"):
                for tb in self.toolboxes_dict.values():
                    if tb.get("image") == image:
                        tb_config = tb
                        break

            cmd = build_server_cmd(
                engine, image, model_path, int(ctx), 
                host, port, kv_dir, kv_mb_val, mtp_model, custom_args,
                role, layers, peer_addr,
                tb_config
            )
            with self.suspend():
                print(f"\nStarting ds4-server with command:\n{' '.join(cmd)}\n")
                print("Press Ctrl+C to stop the server and return to the UI.\n")
                subprocess.run(cmd)

    def _handle_toggle_select_all(self, btn_id: str):
        dt_id = btn_id.replace("btn_toggle_", "")
        dt = self.query_one(f"#{dt_id}", DataTable)

        all_selected = all(
            dt.get_cell_at((i, 1)) in self.selected_toolboxes
            for i in range(dt.row_count)
        )

        for i in range(dt.row_count):
            name = dt.get_cell_at((i, 1))
            if all_selected:
                self.selected_toolboxes.discard(name)
                dt.update_cell_at((i, 0), "\\[ ]")
            else:
                self.selected_toolboxes.add(name)
                dt.update_cell_at((i, 0), "\\[x]")

    def _handle_scan_models(self):
        self.refresh_models()
        self.notify("Local models scanned.", timeout=3)

    def _handle_save_models_path(self):
        new_path = self.query_one("#inp_models_dir", Input).value
        if save_models_dir(new_path):
            self.notify(f"Models directory updated to {new_path}")
            self.refresh_models()
        else:
            self.notify("Failed to save models directory config.", severity="error")

    def _handle_download(self):
        filename = self.query_one("#sel_download_model", SearchableSelect).value
        if not isinstance(filename, str) or not filename:
            return
            
        repo = self.download_repo
        
        if is_model_downloaded(filename):
            self._download_filename = filename
            self.app.push_screen(
                ConfirmModal(f"{filename} appears to be already downloaded.\nDo you want to download it again?"),
                self._on_redownload_confirmed
            )
        else:
            self._do_download_model(repo, filename)

    def _on_redownload_confirmed(self, confirmed: bool) -> None:
        if confirmed:
            self._do_download_model(self.download_repo, self._download_filename)

    def _do_download_model(self, repo: str, filename: str) -> None:
        cmd = get_download_cmd(repo, filename)
        with self.suspend():
            print(f"\nRunning: HF_HUB_ENABLE_HF_TRANSFER=1 {' '.join(cmd)}")
            try:
                env = os.environ.copy()
                env["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
                subprocess.run(cmd, env=env, check=True)
                print("\nDownload Complete!")
            except FileNotFoundError:
                print("\n[ERROR] 'hf' is not installed or not found in PATH.")
            except subprocess.CalledProcessError as e:
                print(f"\n[ERROR] Download failed with exit code {e.returncode}.")
            except Exception as e:
                print(f"\n[ERROR] An unexpected error occurred: {e}")
            try:
                input("\nPress Enter to return to UI...")
            except EOFError:
                pass
        self.refresh_models()

    def _update_toolbox_cell(self, name: str, col: int, value: str):
        for dt in self.query(DataTable):
            if dt.id and dt.id.startswith("dt_"):
                for row_idx in range(dt.row_count):
                    if dt.get_cell_at((row_idx, 1)) == name:
                        dt.update_cell_at((row_idx, col), value)
                        return

    def _get_toolbox_cell(self, name: str, col: int):
        for dt in self.query(DataTable):
            if dt.id and dt.id.startswith("dt_"):
                for row_idx in range(dt.row_count):
                    if dt.get_cell_at((row_idx, 1)) == name:
                        return dt.get_cell_at((row_idx, col))
        return None

    def _on_delete_confirmed(self, confirmed: bool) -> None:
        if confirmed:
            tbs = self._pending_delete_tbs
            with self.suspend():
                for tb in tbs:
                    print(f"Deleting {tb['name']}...")
                    delete_toolbox(tb['name'])
            self.selected_toolboxes.clear()
            self.refresh_toolboxes()

    def _on_update_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return
        to_update = self._pending_update_tbs
        to_create = self._pending_create_tbs
        with self.suspend():
            for tb in to_update:
                delete_toolbox(tb['name'])
        self._do_create_toolboxes(to_create + to_update)

    def _do_create_toolboxes(self, tbs: list) -> None:
        with self.suspend():
            for tb in tbs:
                print(f"\nDownloading and creating toolbox {tb['name']}...")
                create_toolbox(tb['name'], tb['image'], tb.get('args', []))
            input("\nSuccess! Press Enter to return to UI...")
        self.selected_toolboxes.clear()
        self.refresh_toolboxes()

def cli_main():
    app = Ds4CockpitApp()
    app.run()

if __name__ == "__main__":
    cli_main()
