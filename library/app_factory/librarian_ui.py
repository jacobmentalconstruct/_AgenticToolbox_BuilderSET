"""Menu-driven Tkinter librarian UI for catalog browsing and app stamping."""

from __future__ import annotations

import json
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List

from .assistant import AssistantLoopRegistry, AssistantLoopRunner, OllamaAssistantService
from .packs import InstallPackManager
from .query import LibraryQueryService
from .stamper import AppStamper
from .ui_schema import UiSchemaCommitService, UiSchemaPreviewService

THEME = {
    'app_bg': '#14181D',
    'panel_bg': '#1B222B',
    'panel_alt_bg': '#222C38',
    'panel_soft_bg': '#2A3644',
    'field_bg': '#10161E',
    'field_alt_bg': '#16202A',
    'border': '#3A4959',
    'text': '#E7EDF3',
    'muted_text': '#97A6B5',
    'accent': '#C56D3A',
    'accent_hover': '#D9824C',
    'accent_active': '#A65A30',
    'secondary': '#2F7684',
    'secondary_hover': '#3B8FA0',
    'secondary_active': '#275D69',
    'selection': '#35566C',
    'success': '#4FAA80',
    'warning': '#D7A45A',
    'busy': '#E0A458',
}


class LibrarianApp:
    def __init__(self, query_service: LibraryQueryService | None=None):
        self.query_service = query_service or LibraryQueryService()
        self.stamper = AppStamper(self.query_service)
        self.ui_preview = UiSchemaPreviewService()
        self.ui_commit = UiSchemaCommitService()
        self.assistant = OllamaAssistantService()
        self.loop_registry = AssistantLoopRegistry()
        self.loop_runner = AssistantLoopRunner(self.query_service, self.assistant)
        self.pack_manager = InstallPackManager(self.query_service.builder)
        self.root = tk.Tk()
        self.root.title('Library Librarian')
        self.root.geometry('1600x940')
        self._setup_theme()
        self._busy_count = 0
        self.assistant_requires_model: List[ttk.Button] = []
        self.selected_services: List[str] = []
        self.current_services: List[Dict[str, Any]] = []
        self.catalog_service_payload: Dict[str, Any] | None = None
        self.catalog_dependency_payload: Dict[str, Any] | None = None
        self.assistant_session_messages: List[Dict[str, str]] = []
        self.assistant_busy = False
        self.last_assistant_report: Dict[str, Any] | None = None
        self._build_ui()
        self._refresh_services()
        self._reload_assistant_loops()
        self.root.after(150, self._refresh_models)
        self.root.after(
            200,
            lambda: self._append_assistant_message(
                'system',
                'Operator panel ready. Select a service or use the catalog right-click menu to inject context before you chat.',
            ),
        )

    def run(self) -> None:
        self.root.mainloop()

    def _setup_theme(self) -> None:
        self.root.configure(bg=THEME['app_bg'])
        self.root.option_add('*TCombobox*Listbox*Background', THEME['field_bg'])
        self.root.option_add('*TCombobox*Listbox*Foreground', THEME['text'])
        self.root.option_add('*TCombobox*Listbox*selectBackground', THEME['selection'])
        self.root.option_add('*TCombobox*Listbox*selectForeground', THEME['text'])
        style = ttk.Style(self.root)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('.', background=THEME['panel_bg'], foreground=THEME['text'])
        style.configure('TFrame', background=THEME['panel_bg'])
        style.configure('TPanedwindow', background=THEME['app_bg'])
        style.configure('TLabel', background=THEME['panel_bg'], foreground=THEME['text'])
        style.configure('TLabelframe', background=THEME['panel_bg'], bordercolor=THEME['border'])
        style.configure('TLabelframe.Label', background=THEME['panel_bg'], foreground=THEME['text'])
        style.configure('TEntry', fieldbackground=THEME['field_bg'], foreground=THEME['text'])
        style.configure(
            'TCombobox',
            fieldbackground=THEME['field_bg'],
            background=THEME['panel_alt_bg'],
            foreground=THEME['text'],
            arrowcolor=THEME['text'],
            bordercolor=THEME['border'],
        )
        style.map(
            'TCombobox',
            fieldbackground=[('readonly', THEME['field_bg'])],
            background=[('readonly', THEME['panel_alt_bg'])],
            foreground=[('readonly', THEME['text'])],
        )
        style.configure(
            'TButton',
            background=THEME['panel_alt_bg'],
            foreground=THEME['text'],
            bordercolor=THEME['border'],
            padding=(10, 6),
        )
        style.map(
            'TButton',
            background=[('active', THEME['panel_soft_bg']), ('pressed', THEME['secondary_active'])],
            foreground=[('disabled', THEME['muted_text'])],
        )
        style.configure('Accent.TButton', background=THEME['accent'], foreground=THEME['text'], bordercolor=THEME['accent_active'], padding=(10, 6))
        style.map('Accent.TButton', background=[('active', THEME['accent_hover']), ('pressed', THEME['accent_active'])])
        style.configure('Secondary.TButton', background=THEME['secondary'], foreground=THEME['text'], bordercolor=THEME['secondary_active'], padding=(10, 6))
        style.map('Secondary.TButton', background=[('active', THEME['secondary_hover']), ('pressed', THEME['secondary_active'])])
        style.configure(
            'Busy.Horizontal.TProgressbar',
            troughcolor=THEME['field_alt_bg'],
            background=THEME['busy'],
            bordercolor=THEME['border'],
            lightcolor=THEME['busy'],
            darkcolor=THEME['accent_active'],
        )
        style.configure('TNotebook', background=THEME['app_bg'], borderwidth=0, tabmargins=(2, 2, 2, 0))
        style.configure('TNotebook.Tab', background=THEME['panel_alt_bg'], foreground=THEME['muted_text'], padding=(12, 7), borderwidth=0)
        style.map(
            'TNotebook.Tab',
            background=[('selected', THEME['accent']), ('active', THEME['panel_soft_bg'])],
            foreground=[('selected', THEME['text']), ('active', THEME['text'])],
        )

    def _apply_text_theme(self, widget: tk.Text) -> None:
        widget.configure(
            bg=THEME['field_bg'],
            fg=THEME['text'],
            insertbackground=THEME['text'],
            selectbackground=THEME['selection'],
            selectforeground=THEME['text'],
            relief=tk.FLAT,
            borderwidth=0,
            padx=8,
            pady=8,
            highlightthickness=1,
            highlightbackground=THEME['border'],
            highlightcolor=THEME['accent'],
        )

    def _apply_listbox_theme(self, widget: tk.Listbox) -> None:
        widget.configure(
            bg=THEME['field_bg'],
            fg=THEME['text'],
            selectbackground=THEME['selection'],
            selectforeground=THEME['text'],
            activestyle='none',
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=THEME['border'],
            highlightcolor=THEME['accent'],
        )

    def _build_ui(self) -> None:
        shell = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        shell.pack(fill='both', expand=True, padx=8, pady=(8, 0))
        self.assistant_panel = ttk.Frame(shell, padding=(0, 0, 4, 0))
        workspace = ttk.Frame(shell, padding=(4, 0, 0, 0))
        shell.add(self.assistant_panel, weight=2)
        shell.add(workspace, weight=5)

        notebook = ttk.Notebook(workspace)
        notebook.pack(fill='both', expand=True)
        self.catalog_tab = ttk.Frame(notebook)
        self.manifest_tab = ttk.Frame(notebook)
        self.packs_tab = ttk.Frame(notebook)
        notebook.add(self.catalog_tab, text='Catalog')
        notebook.add(self.manifest_tab, text='Manifest')
        notebook.add(self.packs_tab, text='Packs')
        self._build_assistant_panel()
        self._build_catalog_tab()
        self._build_manifest_tab()
        self._build_packs_tab()

        busy_frame = ttk.Frame(self.root, padding=(10, 6))
        busy_frame.pack(fill='x', padx=8, pady=(0, 8))
        self.busy_var = tk.StringVar(value='Ready.')
        self.busy_label = ttk.Label(busy_frame, textvariable=self.busy_var, foreground=THEME['muted_text'])
        self.busy_label.pack(side='left')
        self.busy_progress = ttk.Progressbar(
            busy_frame,
            mode='indeterminate',
            style='Busy.Horizontal.TProgressbar',
            length=160,
        )

    def _set_busy(self, message: str) -> None:
        self._busy_count += 1
        self.busy_var.set(message)
        if not self.busy_progress.winfo_ismapped():
            self.busy_progress.pack(side='right')
        self.busy_progress.start(12)
        self.root.configure(cursor='watch')

    def _clear_busy(self) -> None:
        self._busy_count = max(0, self._busy_count - 1)
        if self._busy_count > 0:
            return
        self.busy_progress.stop()
        if self.busy_progress.winfo_ismapped():
            self.busy_progress.pack_forget()
        self.busy_var.set('Ready.')
        self.root.configure(cursor='')

    def _set_text_content(self, widget: tk.Text, content: str) -> None:
        widget.delete('1.0', tk.END)
        widget.insert(tk.END, content)

    def _run_background_action(
        self,
        worker,
        on_success,
        busy_message: str,
        on_error=None,
    ) -> None:
        def _runner() -> None:
            try:
                result = worker()
            except Exception as exc:
                err = exc
                def _handle_error() -> None:
                    self._clear_busy()
                    if on_error is not None:
                        on_error(err)
                    else:
                        messagebox.showerror('Assistant', str(err))
                self.root.after(0, _handle_error)
                return

            def _handle_success() -> None:
                self._clear_busy()
                on_success(result)

            self.root.after(0, _handle_success)

        self._set_busy(busy_message)
        threading.Thread(target=_runner, daemon=True).start()

    def _build_catalog_tab(self) -> None:
        container = ttk.Frame(self.catalog_tab, padding=8)
        container.pack(fill='both', expand=True)
        panes = ttk.PanedWindow(container, orient=tk.HORIZONTAL)
        panes.pack(fill='both', expand=True)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=5)
        ttk.Label(left, text='Layer').pack(anchor='w')
        self.layer_var = tk.StringVar(value='all')
        self.layer_combo = ttk.Combobox(left, textvariable=self.layer_var, state='readonly')
        self.layer_combo.pack(fill='x', pady=4)
        self.layer_combo.bind('<<ComboboxSelected>>', lambda *_: self._refresh_services())
        self.service_list = tk.Listbox(left, selectmode=tk.EXTENDED)
        self._apply_listbox_theme(self.service_list)
        self.service_list.pack(fill='both', expand=True)
        self.service_list.bind('<<ListboxSelect>>', lambda *_: self._show_selected_service())
        self.service_list.bind('<Button-3>', self._show_service_context_menu)
        self.catalog_context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=THEME['panel_alt_bg'],
            fg=THEME['text'],
            activebackground=THEME['accent'],
            activeforeground=THEME['text'],
            relief=tk.FLAT,
            bd=1,
        )
        self.catalog_context_menu.add_command(label='Inspect Selected Service', command=self._show_selected_service)
        self.catalog_context_menu.add_command(label='Explain Selected Service', command=self._explain_selected_service)
        self.catalog_context_menu.add_command(label='Show Dependencies', command=self._show_selected_dependencies)
        self.catalog_context_menu.add_command(label='Send Context To Assistant', command=self._inject_selected_service_into_assistant)
        self.catalog_context_menu.add_separator()
        self.catalog_context_menu.add_command(label='Recommend Blueprint', command=self._recommend_blueprint)
        button_bar = ttk.Frame(left)
        button_bar.pack(fill='x', pady=6)
        ttk.Button(button_bar, text='Rebuild Catalog', command=self._rebuild_catalog, style='Secondary.TButton').pack(fill='x', pady=2)
        ttk.Button(button_bar, text='Explain Selected', command=self._explain_selected_service, style='Secondary.TButton').pack(fill='x', pady=2)
        ttk.Button(button_bar, text='Show Dependencies', command=self._show_selected_dependencies).pack(fill='x', pady=2)
        ttk.Button(button_bar, text='List UI Components', command=self._list_ui_components).pack(fill='x', pady=2)
        ttk.Button(button_bar, text='List Orchestrators', command=self._list_orchestrators).pack(fill='x', pady=2)
        ttk.Button(button_bar, text='List Managers', command=self._list_managers).pack(fill='x', pady=2)
        ttk.Button(button_bar, text='Send To Assistant', command=self._inject_selected_service_into_assistant, style='Secondary.TButton').pack(fill='x', pady=2)
        ttk.Button(button_bar, text='Recommend Blueprint', command=self._recommend_blueprint, style='Accent.TButton').pack(fill='x', pady=2)

        summary_frame = ttk.LabelFrame(right, text='Selected Service', padding=8)
        summary_frame.pack(fill='x')
        summary_grid = ttk.Frame(summary_frame)
        summary_grid.pack(fill='x', expand=True)
        self.catalog_summary_vars: Dict[str, tk.StringVar] = {}
        summary_fields = [
            ('display_name', 'Name'),
            ('class_name', 'Class'),
            ('layer', 'Layer'),
            ('version', 'Version'),
            ('ui_status', 'UI Service'),
            ('endpoint_count', 'Endpoints'),
            ('dependency_count', 'Dependencies'),
            ('tags', 'Tags'),
            ('capabilities', 'Capabilities'),
            ('import_key', 'Import Key'),
            ('source_path', 'Source Path'),
        ]
        for row_index, (field_key, label_text) in enumerate(summary_fields):
            summary_grid.rowconfigure(row_index, weight=0)
            summary_grid.columnconfigure(1, weight=1)
            ttk.Label(summary_grid, text=label_text).grid(row=row_index, column=0, sticky='nw', padx=(0, 8), pady=2)
            value_var = tk.StringVar(value='-')
            self.catalog_summary_vars[field_key] = value_var
            ttk.Label(
                summary_grid,
                textvariable=value_var,
                justify='left',
                anchor='w',
                wraplength=720,
            ).grid(row=row_index, column=1, sticky='ew', pady=2)

        self.catalog_notebook = ttk.Notebook(right)
        self.catalog_notebook.pack(fill='both', expand=True, pady=(8, 8))
        self.catalog_overview_tab = ttk.Frame(self.catalog_notebook)
        self.catalog_endpoints_tab = ttk.Frame(self.catalog_notebook)
        self.catalog_dependencies_tab = ttk.Frame(self.catalog_notebook)
        self.catalog_source_tab = ttk.Frame(self.catalog_notebook)
        self.catalog_raw_json_tab = ttk.Frame(self.catalog_notebook)
        self.catalog_notebook.add(self.catalog_overview_tab, text='Overview')
        self.catalog_notebook.add(self.catalog_endpoints_tab, text='Endpoints')
        self.catalog_notebook.add(self.catalog_dependencies_tab, text='Dependencies')
        self.catalog_notebook.add(self.catalog_source_tab, text='Source')
        self.catalog_notebook.add(self.catalog_raw_json_tab, text='Raw JSON')
        self.catalog_overview_text = self._create_readonly_text(self.catalog_overview_tab)
        self.catalog_endpoints_text = self._create_readonly_text(self.catalog_endpoints_tab)
        self.catalog_dependencies_text = self._create_readonly_text(self.catalog_dependencies_tab)
        self.catalog_source_text = self._create_readonly_text(self.catalog_source_tab)
        self.catalog_raw_json_text = self._create_readonly_text(self.catalog_raw_json_tab)

        results_frame = ttk.LabelFrame(right, text='Results', padding=8)
        results_frame.pack(fill='both', expand=True)
        self.catalog_results_text = self._create_readonly_text(results_frame, height=10)
        self._clear_catalog_inspector()

    def _build_manifest_tab(self) -> None:
        container = ttk.Frame(self.manifest_tab, padding=8)
        container.pack(fill='both', expand=True)
        controls = ttk.Frame(container)
        controls.pack(fill='x')
        ttk.Label(controls, text='Template').grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.template_options = self.query_service.list_templates()
        self.template_label_to_id = {
            f"{template['template_id']} :: {template['name']}": template['template_id']
            for template in self.template_options
        }
        self.template_var = tk.StringVar(value=next(iter(self.template_label_to_id.keys()), ''))
        self.template_combo = ttk.Combobox(
            controls,
            textvariable=self.template_var,
            state='readonly',
            values=list(self.template_label_to_id.keys()),
        )
        self.template_combo.grid(row=0, column=1, sticky='ew', padx=4, pady=4)
        ttk.Button(controls, text='Load Template', command=self._load_selected_template, style='Secondary.TButton').grid(row=0, column=2, sticky='ew', padx=4, pady=4)
        ttk.Button(controls, text='Stamp Template', command=self._stamp_selected_template, style='Accent.TButton').grid(row=0, column=3, sticky='ew', padx=4, pady=4)
        ttk.Label(controls, text='App Name').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self.app_name_var = tk.StringVar(value='Stamped App')
        ttk.Entry(controls, textvariable=self.app_name_var, width=40).grid(row=1, column=1, sticky='ew', padx=4, pady=4)
        ttk.Label(controls, text='Destination').grid(row=2, column=0, sticky='w', padx=4, pady=4)
        self.destination_var = tk.StringVar(value=str(Path.cwd() / 'stamped_app'))
        ttk.Entry(controls, textvariable=self.destination_var, width=60).grid(row=2, column=1, sticky='ew', padx=4, pady=4)
        ttk.Button(controls, text='Browse', command=self._browse_destination, style='Secondary.TButton').grid(row=2, column=2, sticky='ew', padx=4, pady=4)
        ttk.Label(controls, text='Vendor Mode').grid(row=3, column=0, sticky='w', padx=4, pady=4)
        self.vendor_mode_var = tk.StringVar(value='module_ref')
        ttk.Combobox(controls, textvariable=self.vendor_mode_var, state='readonly', values=['module_ref', 'static']).grid(row=3, column=1, sticky='ew', padx=4, pady=4)
        ttk.Label(controls, text='Resolution').grid(row=4, column=0, sticky='w', padx=4, pady=4)
        self.resolution_var = tk.StringVar(value='app_ready')
        ttk.Combobox(controls, textvariable=self.resolution_var, state='readonly', values=['app_ready', 'strict', 'explicit_pack']).grid(row=4, column=1, sticky='ew', padx=4, pady=4)
        controls.columnconfigure(1, weight=1)
        editors = ttk.PanedWindow(container, orient=tk.HORIZONTAL)
        editors.pack(fill='both', expand=True, pady=8)
        manifest_frame = ttk.Frame(editors)
        schema_frame = ttk.Frame(editors)
        editors.add(manifest_frame, weight=3)
        editors.add(schema_frame, weight=2)
        ttk.Label(manifest_frame, text='app_manifest.json').pack(anchor='w')
        self.manifest_text = tk.Text(manifest_frame, wrap='word')
        self._apply_text_theme(self.manifest_text)
        self.manifest_text.pack(fill='both', expand=True)
        ttk.Label(schema_frame, text='ui_schema.json').pack(anchor='w')
        self.schema_text = tk.Text(schema_frame, wrap='word')
        self._apply_text_theme(self.schema_text)
        self.schema_text.pack(fill='both', expand=True)
        actions = ttk.Frame(container)
        actions.pack(fill='x')
        ttk.Button(actions, text='Load Destination App', command=self._load_destination_app).pack(side='left', padx=4)
        ttk.Button(actions, text='Inspect Destination App', command=self._inspect_destination_app).pack(side='left', padx=4)
        ttk.Button(actions, text='Upgrade Report', command=self._upgrade_report).pack(side='left', padx=4)
        ttk.Button(actions, text='Preview Schema', command=self._preview_schema).pack(side='left', padx=4)
        ttk.Button(actions, text='Validate Manifest', command=self._validate_manifest, style='Secondary.TButton').pack(side='left', padx=4)
        ttk.Button(actions, text='Commit Schema To Destination', command=self._commit_schema).pack(side='left', padx=4)
        ttk.Button(actions, text='Restamp Existing App', command=self._restamp_existing_app, style='Accent.TButton').pack(side='right', padx=4)
        ttk.Button(actions, text='Stamp App', command=self._stamp_manifest, style='Accent.TButton').pack(side='right', padx=4)
        manifest_results = ttk.LabelFrame(container, text='Results', padding=8)
        manifest_results.pack(fill='both', expand=True, pady=(8, 0))
        self.details_text = tk.Text(manifest_results, wrap='word', height=12)
        self._apply_text_theme(self.details_text)
        self.details_text.pack(fill='both', expand=True)

    def _build_assistant_panel(self) -> None:
        container = ttk.Frame(self.assistant_panel, padding=8)
        container.pack(fill='both', expand=True)

        controls = ttk.LabelFrame(container, text='Operator Assistant', padding=8)
        controls.pack(fill='x')
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)

        ttk.Label(controls, text='Model').grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.model_var = tk.StringVar(value='')
        self.model_combo = ttk.Combobox(controls, textvariable=self.model_var, state='readonly')
        self.model_combo.grid(row=0, column=1, sticky='ew', padx=4, pady=4)
        self.model_combo.bind('<<ComboboxSelected>>', lambda *_: self._update_model_stats())

        ttk.Label(controls, text='Loop').grid(row=0, column=2, sticky='w', padx=4, pady=4)
        self.loop_var = tk.StringVar(value='')
        self.loop_combo = ttk.Combobox(controls, textvariable=self.loop_var, state='readonly')
        self.loop_combo.grid(row=0, column=3, sticky='ew', padx=4, pady=4)
        self.loop_combo.bind('<<ComboboxSelected>>', lambda *_: self._on_loop_selected())

        ttk.Label(controls, text='Size Cap (B)').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self.size_cap_var = tk.StringVar(value='14')
        ttk.Entry(controls, textvariable=self.size_cap_var, width=8).grid(row=1, column=1, sticky='w', padx=4, pady=4)

        button_row = ttk.Frame(controls)
        button_row.grid(row=1, column=2, columnspan=2, sticky='e', padx=4, pady=4)
        ttk.Button(button_row, text='Refresh Models', command=self._refresh_models, style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(button_row, text='Refresh Loops', command=self._reload_assistant_loops, style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(button_row, text='Load Loop JSON', command=self._load_loop_json).pack(side='left', padx=2)
        ttk.Button(button_row, text='Inspect Loop', command=self._inspect_selected_loop).pack(side='left', padx=2)

        self.assistant_status_var = tk.StringVar(value='idle')
        self.assistant_context_var = tk.StringVar(value='Context: none')
        self.loop_description_var = tk.StringVar(value='Loop: -')
        self.assistant_stats_vars = {
            'status': tk.StringVar(value='status: -'),
            'processor': tk.StringVar(value='processor: -'),
            'ram': tk.StringVar(value='ram: -'),
            'gpu': tk.StringVar(value='gpu: -'),
            'vram': tk.StringVar(value='vram: -'),
            'context': tk.StringVar(value='ctx: -'),
        }

        ttk.Label(
            controls,
            textvariable=self.assistant_context_var,
            foreground=THEME['muted_text'],
            wraplength=420,
            justify='left',
        ).grid(row=2, column=0, columnspan=4, sticky='ew', padx=4, pady=(2, 0))
        ttk.Label(
            controls,
            textvariable=self.loop_description_var,
            foreground=THEME['muted_text'],
            wraplength=420,
            justify='left',
        ).grid(row=3, column=0, columnspan=4, sticky='ew', padx=4, pady=(0, 2))

        stats_row = ttk.Frame(controls)
        stats_row.grid(row=4, column=0, columnspan=4, sticky='ew', padx=4, pady=(4, 0))
        for key in ['status', 'processor', 'ram', 'gpu', 'vram', 'context']:
            ttk.Label(stats_row, textvariable=self.assistant_stats_vars[key], foreground=THEME['muted_text']).pack(side='left', padx=(0, 10))

        panes = ttk.PanedWindow(container, orient=tk.VERTICAL)
        panes.pack(fill='both', expand=True, pady=(8, 0))

        upper = ttk.PanedWindow(panes, orient=tk.HORIZONTAL)
        panes.add(upper, weight=5)

        history_frame = ttk.LabelFrame(upper, text='Chat History', padding=8)
        trace_frame = ttk.LabelFrame(upper, text='Loop Trace', padding=8)
        upper.add(history_frame, weight=3)
        upper.add(trace_frame, weight=2)

        self.assistant_history_text = tk.Text(history_frame, wrap='word', state='disabled')
        self._apply_text_theme(self.assistant_history_text)
        self.assistant_history_text.pack(fill='both', expand=True)
        self.assistant_history_text.tag_configure('user_header', foreground='#7CC1FF')
        self.assistant_history_text.tag_configure('assistant_header', foreground=THEME['success'])
        self.assistant_history_text.tag_configure('system_header', foreground=THEME['warning'])
        self.assistant_history_text.tag_configure('user_body', foreground=THEME['text'])
        self.assistant_history_text.tag_configure('assistant_body', foreground=THEME['text'])
        self.assistant_history_text.tag_configure('system_body', foreground=THEME['muted_text'])

        self.assistant_trace_text = tk.Text(trace_frame, wrap='word', state='disabled')
        self._apply_text_theme(self.assistant_trace_text)
        self.assistant_trace_text.pack(fill='both', expand=True)

        input_frame = ttk.LabelFrame(panes, text='Prompt', padding=8)
        panes.add(input_frame, weight=2)
        self.assistant_prompt_text = tk.Text(input_frame, wrap='word', height=7)
        self._apply_text_theme(self.assistant_prompt_text)
        self.assistant_prompt_text.pack(fill='both', expand=True)
        self.assistant_prompt_text.bind('<Shift-Return>', self._submit_assistant_prompt_event)

        input_actions = ttk.Frame(input_frame)
        input_actions.pack(fill='x', pady=(8, 0))
        ttk.Label(input_actions, textvariable=self.assistant_status_var, foreground=THEME['muted_text']).pack(side='left')
        summarize_button = ttk.Button(input_actions, text='Use Selected Service', command=self._seed_selected_service_prompt, style='Secondary.TButton')
        summarize_button.pack(side='right', padx=2)
        clear_button = ttk.Button(input_actions, text='Clear Session', command=self._clear_assistant_session)
        clear_button.pack(side='right', padx=2)
        submit_button = ttk.Button(input_actions, text='Submit', command=self._submit_assistant_prompt, style='Accent.TButton')
        submit_button.pack(side='right', padx=2)
        package_button = ttk.Button(input_actions, text='Package Components', command=self._open_package_dialog, style='Secondary.TButton')
        package_button.pack(side='right', padx=2)
        export_button = ttk.Button(input_actions, text='Export Report', command=self._export_assistant_report)
        export_button.pack(side='right', padx=2)
        copy_button = ttk.Button(input_actions, text='Copy Reply', command=self._copy_assistant_reply)
        copy_button.pack(side='right', padx=2)
        self.assistant_requires_model = [submit_button]

    def _build_packs_tab(self) -> None:
        container = ttk.Frame(self.packs_tab, padding=8)
        container.pack(fill='both', expand=True)
        row = ttk.Frame(container)
        row.pack(fill='x')
        ttk.Label(row, text='Pack Source').pack(side='left', padx=4)
        self.pack_source_var = tk.StringVar(value='')
        ttk.Entry(row, textvariable=self.pack_source_var).pack(side='left', fill='x', expand=True, padx=4)
        ttk.Button(row, text='Browse', command=self._browse_pack_source, style='Secondary.TButton').pack(side='left', padx=4)
        ttk.Button(row, text='Install Pack', command=self._install_pack, style='Accent.TButton').pack(side='left', padx=4)
        self.pack_text = tk.Text(container, wrap='word')
        self._apply_text_theme(self.pack_text)
        self.pack_text.pack(fill='both', expand=True, pady=8)

    def _refresh_services(self) -> None:
        layers = ['all'] + self.query_service.list_layers()
        self.layer_combo['values'] = layers
        if self.layer_var.get() not in layers:
            self.layer_var.set('all')
        layer = None if self.layer_var.get() == 'all' else self.layer_var.get()
        services = self.query_service.list_services(layer=layer)
        self.current_services = services
        self.service_list.delete(0, tk.END)
        for service in services:
            self.service_list.insert(tk.END, f"{service['layer']} :: {service['class_name']}")
        self._clear_catalog_inspector()

    def _selected_service_objects(self) -> List[Dict[str, Any]]:
        return [self.current_services[index] for index in self.service_list.curselection()]

    def _show_selected_service(self) -> None:
        selected = self._selected_service_objects()
        if not selected:
            self._clear_catalog_inspector()
            return
        payload = self.query_service.describe_service(selected[0]['class_name'])
        if not payload:
            self._clear_catalog_inspector()
            return
        self.catalog_service_payload = payload
        self.catalog_dependency_payload = payload.get('dependencies')
        self._populate_catalog_inspector(payload)
        self._update_assistant_context_label()

    def _show_selected_dependencies(self) -> None:
        selected = self._selected_service_objects()
        if not selected:
            return
        payload = self.query_service.show_dependencies(selected[0]['class_name'])
        self.catalog_dependency_payload = payload
        if self.catalog_service_payload is not None:
            self._populate_catalog_inspector(self.catalog_service_payload)
        self.catalog_notebook.select(self.catalog_dependencies_tab)
        self._write_catalog_result('Dependency Report', payload)
        self._update_assistant_context_label()

    def _list_ui_components(self) -> None:
        payload = self.query_service.show_ui_components()
        self._write_catalog_result('UI Components', payload)

    def _list_orchestrators(self) -> None:
        payload = self.query_service.list_orchestrators()
        self._write_catalog_result('Orchestrators', payload)

    def _list_managers(self) -> None:
        payload = self.query_service.list_managers()
        self._write_catalog_result('Managers', payload)

    def _rebuild_catalog(self) -> None:
        payload = self.query_service.build_catalog(incremental=True)
        self._refresh_services()
        self._write_catalog_result('Catalog Rebuild', payload)

    def _recommend_blueprint(self) -> None:
        selected = [service['class_name'] for service in self._selected_service_objects()]
        payload = self.query_service.recommend_blueprint(
            selected,
            destination=self.destination_var.get(),
            name=self.app_name_var.get(),
            vendor_mode=self.vendor_mode_var.get(),
            resolution_profile=self.resolution_var.get(),
        )
        self.manifest_text.delete('1.0', tk.END)
        self.manifest_text.insert(tk.END, json.dumps({key: value for key, value in payload.items() if key != 'selected_services'}, indent=2))
        schema = self.ui_preview.default_schema(payload.get('ui_pack', 'headless_pack'))
        self.schema_text.delete('1.0', tk.END)
        self.schema_text.insert(tk.END, json.dumps(schema, indent=2))
        self._write_catalog_result('Recommended Blueprint', payload)

    def _create_readonly_text(self, parent: tk.Widget, height: int=12) -> tk.Text:
        widget = tk.Text(parent, wrap='word', height=height)
        self._apply_text_theme(widget)
        widget.pack(fill='both', expand=True)
        widget.configure(state='disabled')
        return widget

    def _set_readonly_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state='normal')
        widget.delete('1.0', tk.END)
        widget.insert(tk.END, content)
        widget.configure(state='disabled')

    def _clear_catalog_inspector(self) -> None:
        self.catalog_service_payload = None
        self.catalog_dependency_payload = None
        for variable in self.catalog_summary_vars.values():
            variable.set('-')
        empty_message = 'Select a service from the left-hand list to inspect it.'
        self._set_readonly_text(self.catalog_overview_text, empty_message)
        self._set_readonly_text(self.catalog_endpoints_text, empty_message)
        self._set_readonly_text(self.catalog_dependencies_text, empty_message)
        self._set_readonly_text(self.catalog_source_text, empty_message)
        self._set_readonly_text(self.catalog_raw_json_text, empty_message)
        self._set_readonly_text(
            self.catalog_results_text,
            'Action results appear here. Selection details stay in the tabs above.',
        )
        self._update_assistant_context_label()

    def _populate_catalog_inspector(self, payload: Dict[str, Any]) -> None:
        dependencies = self.catalog_dependency_payload or payload.get('dependencies') or {}
        self.catalog_dependency_payload = dependencies
        counts = self._dependency_counts(dependencies)
        self.catalog_summary_vars['display_name'].set(payload.get('service_name') or payload.get('class_name', '-'))
        self.catalog_summary_vars['class_name'].set(payload.get('class_name', '-'))
        self.catalog_summary_vars['layer'].set(payload.get('layer', '-'))
        self.catalog_summary_vars['version'].set(payload.get('version', '-'))
        self.catalog_summary_vars['ui_status'].set('Yes' if self._is_ui_service(payload) else 'No')
        self.catalog_summary_vars['endpoint_count'].set(str(len(payload.get('endpoints', []))))
        self.catalog_summary_vars['dependency_count'].set(
            f"code {counts['code']} | runtime {counts['runtime']} | external {counts['external']}"
        )
        self.catalog_summary_vars['tags'].set(', '.join(payload.get('tags', [])) or '-')
        self.catalog_summary_vars['capabilities'].set(', '.join(payload.get('capabilities', [])) or '-')
        self.catalog_summary_vars['import_key'].set(payload.get('import_key', '-'))
        self.catalog_summary_vars['source_path'].set(payload.get('source_path', '-'))
        self._set_readonly_text(self.catalog_overview_text, self._format_service_overview(payload, dependencies))
        self._set_readonly_text(self.catalog_endpoints_text, self._format_endpoints(payload.get('endpoints', [])))
        self._set_readonly_text(self.catalog_dependencies_text, self._format_dependencies(dependencies))
        self._set_readonly_text(self.catalog_source_text, self._format_source_preview(payload))
        self._set_readonly_text(self.catalog_raw_json_text, json.dumps(payload, indent=2))

    def _dependency_counts(self, dependencies: Dict[str, Any] | None) -> Dict[str, int]:
        payload = dependencies or {}
        return {
            'code': len(payload.get('code_dependencies', [])),
            'runtime': len(payload.get('runtime_dependencies', [])),
            'external': len(payload.get('external_dependencies', [])),
        }

    def _is_ui_service(self, payload: Dict[str, Any]) -> bool:
        return payload.get('layer') == 'ui' or 'ui' in payload.get('tags', []) or any(
            str(capability).startswith('ui:') for capability in payload.get('capabilities', [])
        )

    def _format_service_overview(self, payload: Dict[str, Any], dependencies: Dict[str, Any] | None) -> str:
        counts = self._dependency_counts(dependencies)
        lines = [
            f"Name: {payload.get('service_name') or payload.get('class_name', '-')}",
            f"Class: {payload.get('class_name', '-')}",
            f"Layer: {payload.get('layer', '-')}",
            f"Version: {payload.get('version', '-')}",
            f"UI Service: {'Yes' if self._is_ui_service(payload) else 'No'}",
            '',
            'Purpose',
            '-------',
            payload.get('description') or 'No description recorded.',
            '',
            'Capabilities',
            '------------',
            ', '.join(payload.get('capabilities', [])) or 'None recorded.',
            '',
            'Side Effects',
            '------------',
            ', '.join(payload.get('side_effects', [])) or 'None recorded.',
            '',
            'Dependency Summary',
            '------------------',
            f"Code: {counts['code']}",
            f"Runtime: {counts['runtime']}",
            f"External: {counts['external']}",
        ]
        return '\n'.join(lines)

    def _format_endpoints(self, endpoints: List[Dict[str, Any]]) -> str:
        if not endpoints:
            return 'No endpoints recorded.'
        blocks: List[str] = []
        for endpoint in endpoints:
            blocks.append(
                '\n'.join(
                    [
                        endpoint.get('method_name', '(unknown endpoint)'),
                        f"  Mode: {endpoint.get('mode', '-')}",
                        f"  Inputs: {endpoint.get('inputs_json', '{}')}",
                        f"  Outputs: {endpoint.get('outputs_json', '{}')}",
                        f"  Tags: {endpoint.get('tags_json', '[]')}",
                        f"  Description: {endpoint.get('description', '') or 'No description recorded.'}",
                    ]
                )
            )
        return '\n\n'.join(blocks)

    def _format_dependencies(self, dependencies: Dict[str, Any] | None) -> str:
        if not dependencies:
            return 'No dependency data recorded.'
        sections = [
            ('Code Dependencies', dependencies.get('code_dependencies', [])),
            ('Runtime Dependencies', dependencies.get('runtime_dependencies', [])),
            ('External Dependencies', dependencies.get('external_dependencies', [])),
        ]
        lines: List[str] = []
        for title, items in sections:
            lines.append(title)
            lines.append('-' * len(title))
            if not items:
                lines.append('None.')
            else:
                for item in items:
                    target = item.get('target') or item.get('target_import_key') or '(unresolved)'
                    evidence = item.get('evidence_type', '-')
                    source_path = item.get('target_source_path') or ''
                    lines.append(f"- {target}")
                    lines.append(f"  evidence: {evidence}")
                    if source_path:
                        lines.append(f"  source: {source_path}")
            lines.append('')
        return '\n'.join(lines).strip()

    def _format_source_preview(self, payload: Dict[str, Any]) -> str:
        source_path = Path(str(payload.get('source_path', '')).strip())
        lines = [
            f"Import Key: {payload.get('import_key', '-')}",
            f"Source Path: {source_path if source_path else '-'}",
            '',
        ]
        if not source_path or not source_path.exists():
            lines.append('Source preview unavailable.')
            return '\n'.join(lines)
        try:
            source_text = source_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            source_text = source_path.read_text(encoding='utf-8', errors='replace')
        source_lines = source_text.splitlines()
        preview_limit = 80
        preview = source_lines[:preview_limit]
        lines.append('Preview')
        lines.append('-------')
        lines.extend(f'{index + 1:>4}: {line}' for index, line in enumerate(preview))
        if len(source_lines) > preview_limit:
            lines.append('')
            lines.append(f'... truncated after {preview_limit} lines')
        return '\n'.join(lines)

    def _write_catalog_result(self, title: str, payload: Any) -> None:
        if isinstance(payload, str):
            body = payload
        else:
            body = json.dumps(payload, indent=2)
        content = f'{title}\n{"=" * len(title)}\n{body}'
        self._set_readonly_text(self.catalog_results_text, content)

    def _show_service_context_menu(self, event: tk.Event) -> None:
        if self.service_list.size() == 0:
            return
        index = self.service_list.nearest(event.y)
        if index < 0:
            return
        self.service_list.selection_clear(0, tk.END)
        self.service_list.selection_set(index)
        self.service_list.activate(index)
        self._show_selected_service()
        try:
            self.catalog_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.catalog_context_menu.grab_release()

    def _resolve_assistant_model(self) -> str:
        model_name = self.model_var.get().strip()
        if model_name:
            return model_name
        try:
            cap = float(self.size_cap_var.get())
        except ValueError:
            cap = 14.0
        default = self.assistant.choose_default_model(cap)
        if default:
            self.model_var.set(default)
            self._update_model_stats()
        return default or ''

    def _update_assistant_model_state(self) -> None:
        enabled = bool(self._resolve_assistant_model())
        for button in self.assistant_requires_model:
            if enabled:
                button.state(['!disabled'])
            else:
                button.state(['disabled'])
        if hasattr(self, 'assistant_status_var') and self.assistant_status_var.get() in {'idle', 'missing'}:
            self.assistant_status_var.set('idle' if enabled else 'missing model')

    def _deterministic_service_explanation(self, payload: Dict[str, Any], dependencies: Dict[str, Any] | None) -> str:
        counts = self._dependency_counts(dependencies)
        endpoint_names = [endpoint.get('method_name', '-') for endpoint in payload.get('endpoints', [])]
        lines = [
            f"{payload.get('service_name') or payload.get('class_name', 'This service')} is a {payload.get('layer', 'general')} microservice.",
            payload.get('description') or 'No description recorded.',
            '',
            f"Version: {payload.get('version', '-')}",
            f"Primary endpoints: {', '.join(endpoint_names) if endpoint_names else 'none recorded'}",
            f"Capabilities: {', '.join(payload.get('capabilities', [])) or 'none recorded'}",
            f"Code dependencies: {counts['code']}",
            f"Runtime dependencies: {counts['runtime']}",
            f"External dependencies: {counts['external']}",
        ]
        if payload.get('tags'):
            lines.append(f"Tags: {', '.join(payload.get('tags', []))}")
        if payload.get('side_effects'):
            lines.append(f"Side effects: {', '.join(payload.get('side_effects', []))}")
        return '\n'.join(lines)

    def _explain_selected_service(self) -> None:
        selected = self._selected_service_objects()
        if not selected:
            messagebox.showwarning('Explain Selected Service', 'Select a service first.')
            return
        payload = self.query_service.describe_service(selected[0]['class_name'])
        if not payload:
            messagebox.showwarning('Explain Selected Service', 'Could not resolve the selected service.')
            return
        self.catalog_service_payload = payload
        self.catalog_dependency_payload = payload.get('dependencies') or self.query_service.show_dependencies(selected[0]['class_name'])
        self._populate_catalog_inspector(payload)
        self._update_assistant_context_label()
        fallback = self._deterministic_service_explanation(payload, self.catalog_dependency_payload)
        model_name = self._resolve_assistant_model()
        if model_name:
            pending = f'Running {model_name} on the selected service...'
            self._append_assistant_message('system', pending)
            self._write_catalog_result('Assistant Summary', pending)
            self.assistant_status_var.set('summarizing')

            def _worker():
                return self.assistant.summarize_service(model_name, payload)

            def _on_success(result):
                final_output = fallback
                title = 'Service Explanation'
                if result.get('ok') and result.get('output', '').strip():
                    final_output = result['output']
                    title = f'Assistant Summary ({model_name})'
                else:
                    failure_note = result.get('error', '').strip() or 'Assistant response was empty.'
                    final_output = f'Assistant fallback reason: {failure_note}\n\n{fallback}'
                self.assistant_status_var.set('idle')
                self._append_assistant_message('assistant', final_output)
                self._write_assistant_trace({'action': 'assistant_summary', 'model': model_name, 'result': result})
                self._write_catalog_result(title, final_output)

            self._run_background_action(
                _worker,
                _on_success,
                f'Inferring with {model_name}...',
                on_error=lambda exc: self._fail_assistant_run(str(exc)),
            )
            return
        self.assistant_status_var.set('idle')
        self._append_assistant_message('assistant', fallback)
        self._write_assistant_trace({'action': 'deterministic_service_explanation', 'service': payload})
        self._write_catalog_result('Service Explanation', fallback)

    def _load_selected_template(self) -> None:
        try:
            label = self.template_var.get().strip()
            template_id = self.template_label_to_id.get(label, '')
            if not template_id:
                messagebox.showwarning('Load Template', 'Select a template first.')
                return
            payload = self.query_service.template_blueprint(
                template_id,
                destination=self.destination_var.get(),
                name=self.app_name_var.get(),
                vendor_mode=self.vendor_mode_var.get(),
                resolution_profile=self.resolution_var.get(),
            )
            self.app_name_var.set(payload.get('name', self.app_name_var.get()))
            self.vendor_mode_var.set(payload.get('vendor_mode', self.vendor_mode_var.get()))
            self.resolution_var.set(payload.get('resolution_profile', self.resolution_var.get()))
            self.manifest_text.delete('1.0', tk.END)
            self.manifest_text.insert(tk.END, json.dumps({key: value for key, value in payload.items() if key != 'selected_services'}, indent=2))
            schema = self.ui_preview.default_schema(payload.get('ui_pack', 'headless_pack'))
            self.schema_text.delete('1.0', tk.END)
            self.schema_text.insert(tk.END, json.dumps(schema, indent=2))
            self.details_text.delete('1.0', tk.END)
            self.details_text.insert(tk.END, json.dumps(payload, indent=2))
        except Exception as exc:
            messagebox.showerror('Load Template', str(exc))

    def _stamp_selected_template(self) -> None:
        try:
            label = self.template_var.get().strip()
            template_id = self.template_label_to_id.get(label, '')
            if not template_id:
                messagebox.showwarning('Stamp Template', 'Select a template first.')
                return
            payload = self.query_service.template_blueprint(
                template_id,
                destination=self.destination_var.get(),
                name=self.app_name_var.get(),
                vendor_mode=self.vendor_mode_var.get(),
                resolution_profile=self.resolution_var.get(),
            )
            report = self.stamper.stamp(payload)
            self.manifest_text.delete('1.0', tk.END)
            self.manifest_text.insert(tk.END, json.dumps({key: value for key, value in payload.items() if key != 'selected_services'}, indent=2))
            schema = self.ui_preview.default_schema(payload.get('ui_pack', 'headless_pack'))
            self.schema_text.delete('1.0', tk.END)
            self.schema_text.insert(tk.END, json.dumps(schema, indent=2))
            self.details_text.delete('1.0', tk.END)
            self.details_text.insert(tk.END, json.dumps(report, indent=2))
            if report['validation']['ok']:
                messagebox.showinfo('Stamp Template', f"Stamped app at {report['app_dir']}")
            else:
                messagebox.showwarning('Stamp Template', 'Stamp completed with validation errors. See details.')
        except Exception as exc:
            messagebox.showerror('Stamp Template', str(exc))

    def _browse_destination(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.destination_var.get() or str(Path.cwd()))
        if selected:
            self.destination_var.set(selected)

    def _preview_schema(self) -> None:
        try:
            schema = json.loads(self.schema_text.get('1.0', tk.END).strip())
            self.ui_preview.render_preview(self.root, schema)
        except Exception as exc:
            messagebox.showerror('Preview Schema', str(exc))

    def _load_destination_app(self) -> None:
        try:
            app_dir = Path(self.destination_var.get()).resolve()
            manifest = self.stamper.load_app_manifest(app_dir)
            self.app_name_var.set(manifest.get('name', self.app_name_var.get()))
            self.vendor_mode_var.set(manifest.get('vendor_mode', self.vendor_mode_var.get()))
            self.resolution_var.set(manifest.get('resolution_profile', self.resolution_var.get()))
            self.manifest_text.delete('1.0', tk.END)
            self.manifest_text.insert(tk.END, json.dumps(manifest, indent=2))
            schema_path = app_dir / 'ui_schema.json'
            if schema_path.exists():
                schema = json.loads(schema_path.read_text(encoding='utf-8'))
                self.schema_text.delete('1.0', tk.END)
                self.schema_text.insert(tk.END, json.dumps(schema, indent=2))
            self.details_text.delete('1.0', tk.END)
            self.details_text.insert(tk.END, json.dumps({'loaded_app_dir': str(app_dir), 'manifest': manifest}, indent=2))
        except Exception as exc:
            messagebox.showerror('Load Destination App', str(exc))

    def _inspect_destination_app(self) -> None:
        try:
            report = self.stamper.inspect_app(Path(self.destination_var.get()))
            self.details_text.delete('1.0', tk.END)
            self.details_text.insert(tk.END, json.dumps(report, indent=2))
            if report['errors']:
                messagebox.showwarning('Inspect Destination App', 'Inspection found issues. See details.')
            else:
                messagebox.showinfo('Inspect Destination App', 'Inspection completed.')
        except Exception as exc:
            messagebox.showerror('Inspect Destination App', str(exc))

    def _upgrade_report(self) -> None:
        try:
            report = self.stamper.upgrade_report(Path(self.destination_var.get()))
            self.details_text.delete('1.0', tk.END)
            self.details_text.insert(tk.END, json.dumps(report, indent=2))
            if report['inspection']['errors']:
                messagebox.showwarning('Upgrade Report', 'Upgrade report found blocking issues. See details.')
            elif report['upgrade_recommended']:
                messagebox.showinfo('Upgrade Report', 'Differences found. Review the report before restamping.')
            else:
                messagebox.showinfo('Upgrade Report', 'No upgrade changes detected.')
        except Exception as exc:
            messagebox.showerror('Upgrade Report', str(exc))

    def _commit_schema(self) -> None:
        try:
            schema = json.loads(self.schema_text.get('1.0', tk.END).strip())
            target = self.ui_commit.commit(schema, Path(self.destination_var.get()))
            messagebox.showinfo('Commit Schema', f'Wrote {target}')
        except Exception as exc:
            messagebox.showerror('Commit Schema', str(exc))

    def _stamp_manifest(self) -> None:
        try:
            payload = json.loads(self.manifest_text.get('1.0', tk.END).strip())
            payload['destination'] = self.destination_var.get()
            payload['name'] = self.app_name_var.get()
            payload['vendor_mode'] = self.vendor_mode_var.get()
            payload['resolution_profile'] = self.resolution_var.get()
            validation = self.query_service.validate_manifest(payload)
            if not validation['ok']:
                self.details_text.delete('1.0', tk.END)
                self.details_text.insert(tk.END, json.dumps(validation, indent=2))
                messagebox.showwarning('Stamp App', 'Manifest validation failed. See details.')
                return
            report = self.stamper.stamp(payload)
            self.details_text.delete('1.0', tk.END)
            self.details_text.insert(tk.END, json.dumps(report, indent=2))
            if report['validation']['ok']:
                messagebox.showinfo('Stamp App', f"Stamped app at {report['app_dir']}")
            else:
                messagebox.showwarning('Stamp App', 'Stamp completed with validation errors. See details.')
        except Exception as exc:
            messagebox.showerror('Stamp App', str(exc))

    def _validate_manifest(self) -> None:
        try:
            payload = json.loads(self.manifest_text.get('1.0', tk.END).strip())
            payload['destination'] = self.destination_var.get()
            payload['name'] = self.app_name_var.get()
            payload['vendor_mode'] = self.vendor_mode_var.get()
            payload['resolution_profile'] = self.resolution_var.get()
            report = self.query_service.validate_manifest(payload)
            self.details_text.delete('1.0', tk.END)
            self.details_text.insert(tk.END, json.dumps(report, indent=2))
            if report['ok']:
                messagebox.showinfo('Validate Manifest', 'Manifest validation passed.')
            else:
                messagebox.showwarning('Validate Manifest', 'Manifest validation failed. See details.')
        except Exception as exc:
            messagebox.showerror('Validate Manifest', str(exc))

    def _restamp_existing_app(self) -> None:
        try:
            report = self.stamper.restamp_existing_app(
                Path(self.destination_var.get()),
                preserve_ui_schema=True,
            )
            self.details_text.delete('1.0', tk.END)
            self.details_text.insert(tk.END, json.dumps(report, indent=2))
            if report['validation']['ok']:
                messagebox.showinfo('Restamp Existing App', f"Restamped app at {report['app_dir']}")
            else:
                messagebox.showwarning('Restamp Existing App', 'Restamp completed with validation errors. See details.')
        except Exception as exc:
            messagebox.showerror('Restamp Existing App', str(exc))

    def _refresh_models(self) -> None:
        try:
            cap = float(self.size_cap_var.get())
        except ValueError:
            cap = 14.0
        models = self.assistant.list_models()
        self.model_combo['values'] = [model['name'] for model in models]
        current = self.model_var.get().strip()
        default = self.assistant.choose_default_model(cap) if not current else current
        if default and default in self.model_combo['values']:
            self.model_var.set(default)
        else:
            self.model_var.set('')
        self._update_model_stats()
        self._update_assistant_model_state()
        self._write_assistant_trace({'action': 'refresh_models', 'models': models})

    def _assistant_summarize(self) -> None:
        self._explain_selected_service()

    def _assistant_schema(self) -> None:
        model_name = self._resolve_assistant_model()
        if not model_name:
            messagebox.showwarning('Assistant', 'Select an Ollama model first.')
            return
        try:
            schema = json.loads(self.schema_text.get('1.0', tk.END).strip())
        except Exception as exc:
            messagebox.showerror('Assistant', str(exc))
            return
        pending = f'Generating a schema suggestion with {model_name}...'
        self.assistant_status_var.set('schema')
        self._append_assistant_message('system', pending)
        self._write_catalog_result('Assistant Schema Suggestion', pending)

        def _worker():
            return self.assistant.suggest_ui_schema(model_name, schema, 'Improve clarity and usability for a stamped Tkinter app.')

        def _on_success(result):
            self.assistant_status_var.set('idle')
            final_output = result.get('output', '').strip() or json.dumps(result, indent=2)
            self._append_assistant_message('assistant', final_output)
            self._write_assistant_trace({'action': 'assistant_schema', 'model': model_name, 'result': result})
            self._write_catalog_result('Assistant Schema Suggestion', final_output)

        self._run_background_action(
            _worker,
            _on_success,
            f'Generating UI schema with {model_name}...',
            on_error=lambda exc: self._fail_assistant_run(str(exc)),
        )

    def _reload_assistant_loops(self) -> None:
        report = self.loop_registry.reload()
        loops = self.loop_registry.list_loops()
        self.loop_combo['values'] = [loop['loop_id'] for loop in loops]
        if not self.loop_var.get().strip() or self.loop_var.get().strip() not in self.loop_combo['values']:
            if loops:
                self.loop_var.set(loops[0]['loop_id'])
        self._on_loop_selected()
        self._write_assistant_trace({'action': 'reload_loops', 'report': report, 'loops': loops})

    def _load_loop_json(self) -> None:
        selected = filedialog.askopenfilename(
            title='Select loop JSON',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
        )
        if not selected:
            return
        try:
            report = self.loop_registry.import_loop_file(selected)
            self._reload_assistant_loops()
            self._append_assistant_message('system', f'Loaded loop file: {report["path"]}')
        except Exception as exc:
            messagebox.showerror('Load Loop JSON', str(exc))

    def _inspect_selected_loop(self) -> None:
        loop_spec = self.loop_registry.get_loop(self.loop_var.get().strip())
        if not loop_spec:
            return
        self._write_assistant_trace({'action': 'inspect_loop', 'loop': loop_spec})

    def _on_loop_selected(self) -> None:
        loop_spec = self.loop_registry.get_loop(self.loop_var.get().strip())
        if not loop_spec:
            self.loop_description_var.set('Loop: -')
            return
        self.loop_description_var.set(
            f"{loop_spec['name']} [{loop_spec['source']}] - {loop_spec['description'] or 'No description.'}"
        )

    def _update_model_stats(self) -> None:
        details = self.assistant.describe_model(self.model_var.get().strip())
        self.assistant_stats_vars['status'].set(f"status: {details.get('status', '-')}")
        self.assistant_stats_vars['processor'].set(f"processor: {details.get('processor', '-')}")
        self.assistant_stats_vars['ram'].set(f"ram: {details.get('ram', '-')}")
        self.assistant_stats_vars['gpu'].set(f"gpu: {details.get('gpu', '-')}")
        self.assistant_stats_vars['vram'].set(f"vram: {details.get('vram', '-')}")
        self.assistant_stats_vars['context'].set(f"ctx: {details.get('context_length', '-')}")

    def _update_assistant_context_label(self) -> None:
        payload = self.catalog_service_payload or {}
        if payload:
            self.assistant_context_var.set(
                f"Context: {payload.get('class_name', '-')} [{payload.get('layer', '-')}] via catalog selection"
            )
            return
        self.assistant_context_var.set('Context: none')

    def _selected_assistant_service_context(self) -> Dict[str, Any] | None:
        if self.catalog_service_payload:
            return self.catalog_service_payload
        selected = self._selected_service_objects()
        if not selected:
            return None
        payload = self.query_service.describe_service(selected[0]['class_name'])
        if payload:
            self.catalog_service_payload = payload
            self.catalog_dependency_payload = payload.get('dependencies')
            self._update_assistant_context_label()
        return payload

    def _seed_selected_service_prompt(self) -> None:
        payload = self._selected_assistant_service_context()
        if not payload:
            messagebox.showwarning('Assistant', 'Select a service first.')
            return
        seed = (
            f"Investigate {payload.get('class_name', '')}.\n"
            f"Focus on purpose, dependencies, and how it fits into the library."
        )
        self.assistant_prompt_text.delete('1.0', tk.END)
        self.assistant_prompt_text.insert(tk.END, seed)
        self.assistant_prompt_text.focus_set()

    def _inject_selected_service_into_assistant(self) -> None:
        payload = self._selected_assistant_service_context()
        if not payload:
            return
        self._append_assistant_message(
            'system',
            f"Injected context target: {payload.get('class_name', '-')} [{payload.get('layer', '-')}]",
        )
        self._write_assistant_trace({'action': 'inject_context', 'selected_service': payload})

    def _submit_assistant_prompt_event(self, event: tk.Event) -> str:
        self._submit_assistant_prompt()
        return 'break'

    def _submit_assistant_prompt(self) -> None:
        if self.assistant_busy:
            return
        prompt = self.assistant_prompt_text.get('1.0', tk.END).strip()
        if not prompt:
            return
        loop_spec = self.loop_registry.get_loop(self.loop_var.get().strip())
        if not loop_spec:
            messagebox.showwarning('Assistant', 'Select a loop first.')
            return
        model_name = self._resolve_assistant_model()
        selected_context = self._selected_assistant_service_context()
        self.assistant_prompt_text.delete('1.0', tk.END)
        self.assistant_session_messages.append({'role': 'user', 'content': prompt})
        self._append_assistant_message('user', prompt)
        self.assistant_busy = True
        self.assistant_status_var.set(f"running {loop_spec['loop_id']}")

        def _worker():
            return self.loop_runner.run_loop(
                loop_spec=loop_spec,
                user_prompt=prompt,
                model_name=model_name,
                selected_service=selected_context,
                chat_history=self.assistant_session_messages[:-1],
            )

        self._run_background_action(
            _worker,
            self._finish_assistant_run,
            f"Running {loop_spec['loop_id']}...",
            on_error=lambda exc: self._fail_assistant_run(str(exc)),
        )

    def _finish_assistant_run(self, report: Dict[str, Any]) -> None:
        self.assistant_busy = False
        self.last_assistant_report = report
        self.assistant_status_var.set('idle')
        reply = report.get('assistant_output', '').strip()
        if reply:
            self.assistant_session_messages.append({'role': 'assistant', 'content': reply})
            self._append_assistant_message('assistant', reply)
        max_history = max(1, int(report.get('max_history_messages', 8) or 8))
        self.assistant_session_messages = self.assistant_session_messages[-max_history:]
        self._write_assistant_trace(report)

    def _fail_assistant_run(self, error_text: str) -> None:
        self.assistant_busy = False
        self.assistant_status_var.set('error')
        self._append_assistant_message('system', f'Assistant error: {error_text}')
        self._write_assistant_trace({'action': 'assistant_error', 'error': error_text})

    def _copy_assistant_reply(self) -> None:
        report = self.last_assistant_report
        if not report:
            messagebox.showinfo('Copy Reply', 'No assistant reply yet.')
            return
        reply = str(report.get('assistant_output', '')).strip()
        if not reply:
            messagebox.showinfo('Copy Reply', 'Last reply was empty.')
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(reply)
        self.assistant_status_var.set('Reply copied to clipboard.')

    def _export_assistant_report(self) -> None:
        report = self.last_assistant_report
        if not report:
            messagebox.showinfo('Export Report', 'No assistant report yet.')
            return
        path = filedialog.asksaveasfilename(
            title='Export Assistant Report',
            defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
        )
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(report, indent=2), encoding='utf-8')
            self.assistant_status_var.set(f'Report exported to {path}')
        except OSError as exc:
            messagebox.showerror('Export Report', str(exc))

    def _clear_assistant_session(self) -> None:
        self.assistant_session_messages = []
        self.last_assistant_report = None
        self._set_text_widget(self.assistant_history_text, '')
        self._set_text_widget(self.assistant_trace_text, '')
        self.assistant_status_var.set('idle')

    def _append_assistant_message(self, role: str, content: str) -> None:
        body = str(content).strip()
        if not body:
            return
        widget = self.assistant_history_text
        widget.configure(state='normal')
        widget.insert(tk.END, f'{role.upper()}\n', f'{role}_header')
        widget.insert(tk.END, body + '\n\n', f'{role}_body')
        widget.configure(state='disabled')
        widget.see(tk.END)

    def _write_assistant_trace(self, payload: Any) -> None:
        content = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
        self._set_text_widget(self.assistant_trace_text, content)

    def _set_text_widget(self, widget: tk.Text, content: str) -> None:
        widget.configure(state='normal')
        widget.delete('1.0', tk.END)
        widget.insert(tk.END, content)
        widget.configure(state='disabled')

    def _browse_pack_source(self) -> None:
        selected = filedialog.askopenfilename(title='Select pack zip or folder')
        if not selected:
            selected = filedialog.askdirectory(title='Select pack folder')
        if selected:
            self.pack_source_var.set(selected)

    def _install_pack(self) -> None:
        source = self.pack_source_var.get().strip()
        if not source:
            return
        try:
            report = self.pack_manager.install(source)
            self.pack_text.delete('1.0', tk.END)
            self.pack_text.insert(tk.END, json.dumps(report, indent=2))
            self._refresh_services()
        except Exception as exc:
            messagebox.showerror('Install Pack', str(exc))

    # ── Component packaging ──────────────────────────────────

    def _extract_components_from_report(self, report: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract a deduplicated list of components from the last assistant report.

        Pulls from both the search results and the blueprint recommendation.
        Returns list of dicts with keys: class_name, layer, description, source_path.
        """
        seen: set[str] = set()
        components: List[Dict[str, str]] = []
        steps = report.get('steps', {})
        if not isinstance(steps, dict):
            return components
        # From recommend_blueprint step
        blueprint = steps.get('recommended_blueprint', {})
        if isinstance(blueprint, dict):
            for svc in blueprint.get('selected_services', []):
                cn = str(svc.get('class_name', '')).strip()
                if cn and cn not in seen:
                    seen.add(cn)
                    components.append({
                        'class_name': cn,
                        'layer': str(svc.get('layer', '')),
                        'description': str(svc.get('description', '')),
                        'source_path': str(svc.get('source_path', '')),
                    })
        # From service_search step
        search = steps.get('service_search', {})
        if isinstance(search, dict):
            for match in search.get('matches', []):
                cn = str(match.get('class_name', '')).strip()
                if cn and cn not in seen:
                    seen.add(cn)
                    components.append({
                        'class_name': cn,
                        'layer': str(match.get('layer', '')),
                        'description': str(match.get('description', '')),
                        'source_path': str(match.get('source_path', '')),
                    })
        return components

    def _open_package_dialog(self) -> None:
        report = self.last_assistant_report
        if not report:
            messagebox.showinfo('Package Components', 'Run a loop first to get recommendations.')
            return
        components = self._extract_components_from_report(report)
        if not components:
            messagebox.showinfo('Package Components', 'No components found in the last report.')
            return
        PackageComponentsDialog(self.root, components)


class PackageComponentsDialog:
    """Modal dialog for selecting recommended components and exporting them as a .zip."""

    def __init__(self, parent: tk.Tk, components: List[Dict[str, str]]):
        self.components = components
        self.dialog = tk.Toplevel(parent)
        self.dialog.title('Package Components')
        self.dialog.geometry('720x520')
        self.dialog.configure(bg=THEME['app_bg'])
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.check_vars: List[tk.BooleanVar] = []
        self._build_ui()

    def _build_ui(self) -> None:
        header = tk.Label(
            self.dialog, text='Select components to package',
            bg=THEME['app_bg'], fg=THEME['text'], font=('Segoe UI Semibold', 11),
        )
        header.pack(anchor='w', padx=12, pady=(12, 4))

        # Select all / none controls
        select_row = tk.Frame(self.dialog, bg=THEME['app_bg'])
        select_row.pack(fill='x', padx=12, pady=(0, 4))
        tk.Button(select_row, text='Select All', command=self._select_all,
                  bg=THEME['panel_alt_bg'], fg=THEME['text'], relief='flat', padx=8).pack(side='left')
        tk.Button(select_row, text='Select None', command=self._select_none,
                  bg=THEME['panel_alt_bg'], fg=THEME['text'], relief='flat', padx=8).pack(side='left', padx=(6, 0))

        # Scrollable component list
        list_frame = tk.Frame(self.dialog, bg=THEME['panel_bg'])
        list_frame.pack(fill='both', expand=True, padx=12, pady=4)

        canvas = tk.Canvas(list_frame, bg=THEME['panel_bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        self.inner_frame = tk.Frame(canvas, bg=THEME['panel_bg'])

        self.inner_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self.inner_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        for component in self.components:
            var = tk.BooleanVar(value=True)
            self.check_vars.append(var)
            row = tk.Frame(self.inner_frame, bg=THEME['panel_bg'])
            row.pack(fill='x', padx=4, pady=2)
            cb = tk.Checkbutton(
                row, variable=var, bg=THEME['panel_bg'], fg=THEME['text'],
                selectcolor=THEME['field_bg'], activebackground=THEME['panel_bg'],
                activeforeground=THEME['text'],
            )
            cb.pack(side='left')
            label_text = component['class_name']
            if component.get('layer'):
                label_text += f"  [{component['layer']}]"
            tk.Label(row, text=label_text, bg=THEME['panel_bg'], fg=THEME['text'],
                     font=('Segoe UI Semibold', 9)).pack(side='left')
            if component.get('description'):
                desc = component['description']
                if len(desc) > 90:
                    desc = desc[:87] + '...'
                tk.Label(row, text=f'  {desc}', bg=THEME['panel_bg'],
                         fg=THEME['muted_text'], font=('Segoe UI', 8)).pack(side='left', padx=(4, 0))

        # Destination + export
        bottom = tk.Frame(self.dialog, bg=THEME['app_bg'])
        bottom.pack(fill='x', padx=12, pady=(8, 12))

        self.dest_var = tk.StringVar(value='')
        dest_row = tk.Frame(bottom, bg=THEME['app_bg'])
        dest_row.pack(fill='x', pady=(0, 8))
        tk.Label(dest_row, text='Save to:', bg=THEME['app_bg'], fg=THEME['text']).pack(side='left')
        tk.Entry(dest_row, textvariable=self.dest_var, bg=THEME['field_bg'],
                 fg=THEME['text'], insertbackground=THEME['text'], relief='flat').pack(side='left', fill='x', expand=True, padx=(8, 8))
        tk.Button(dest_row, text='Browse', command=self._browse_destination,
                  bg=THEME['panel_alt_bg'], fg=THEME['text'], relief='flat', padx=8).pack(side='left')

        self.status_var = tk.StringVar(value='')
        tk.Label(bottom, textvariable=self.status_var, bg=THEME['app_bg'],
                 fg=THEME['muted_text']).pack(side='left')
        tk.Button(bottom, text='Export .zip', command=self._export_zip,
                  bg=THEME['accent'], fg=THEME['text'], relief='flat',
                  padx=16, pady=4, font=('Segoe UI Semibold', 10)).pack(side='right')

    def _select_all(self) -> None:
        for var in self.check_vars:
            var.set(True)

    def _select_none(self) -> None:
        for var in self.check_vars:
            var.set(False)

    def _browse_destination(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.dialog,
            title='Save component package as',
            defaultextension='.zip',
            filetypes=[('Zip archives', '*.zip'), ('All files', '*.*')],
        )
        if path:
            self.dest_var.set(path)

    def _export_zip(self) -> None:
        dest = self.dest_var.get().strip()
        if not dest:
            messagebox.showwarning('Export', 'Choose a destination first.', parent=self.dialog)
            return
        selected = [
            comp for comp, var in zip(self.components, self.check_vars)
            if var.get()
        ]
        if not selected:
            messagebox.showwarning('Export', 'Select at least one component.', parent=self.dialog)
            return

        dest_path = Path(dest)
        missing: List[str] = []
        written: List[str] = []
        try:
            with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for comp in selected:
                    src = Path(comp['source_path'])
                    if not src.exists():
                        missing.append(comp['class_name'])
                        continue
                    arcname = f"{comp.get('layer', 'unknown')}/{src.name}"
                    zf.write(src, arcname)
                    written.append(comp['class_name'])
                # Include a manifest of what was packaged
                manifest = {
                    'components': [
                        {
                            'class_name': c['class_name'],
                            'layer': c.get('layer', ''),
                            'description': c.get('description', ''),
                            'source_file': f"{c.get('layer', 'unknown')}/{Path(c['source_path']).name}",
                        }
                        for c in selected if c['class_name'] in written
                    ],
                    'missing': missing,
                }
                zf.writestr('manifest.json', json.dumps(manifest, indent=2))
        except OSError as exc:
            messagebox.showerror('Export', str(exc), parent=self.dialog)
            return

        parts = [f'Packaged {len(written)} component(s) to {dest_path.name}.']
        if missing:
            parts.append(f'{len(missing)} source file(s) not found: {", ".join(missing)}')
        self.status_var.set(parts[0])
        messagebox.showinfo('Export Complete', '\n'.join(parts), parent=self.dialog)
