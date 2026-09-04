"""Tkinter GUI for the validated VCU tuner backend."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .firmware import FirmwareDocument, FirmwareError, bundled_template_details, encode_thumb_imm, validate_ota_template
from .i18n import localize_error, tr

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


def settings_path() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home()))
    return root / "NinebotVCUTuner" / "settings.json"


def load_language() -> str:
    try:
        value = json.loads(settings_path().read_text(encoding="utf-8")).get("language")
        return value if value in ("en", "ru") else "en"
    except (OSError, json.JSONDecodeError, AttributeError):
        return "en"


def save_language(language: str) -> None:
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"language": language}, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def default_output_stem(document: FirmwareDocument) -> str:
    version = re.sub(r"[^A-Za-z0-9._-]+", "_", document.profile.version)
    if document.trust == "exact":
        return f"VCU_{version}_variant0_tuned"
    return f"{document.path.stem}_VCU_{version}_derivative_tuned"


class TunerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.language = load_language()
        self.document: FirmwareDocument | None = None
        self.custom_template: Path | None = None
        self.pair_vars: dict[str, tuple[tk.StringVar, tk.StringVar]] = {}
        self.scalar_vars: dict[str, tk.StringVar] = {}
        self.drop_supported = bool(DND_FILES and hasattr(root, "drop_target_register"))
        root.geometry("1020x820")
        root.minsize(760, 560)
        self._configure_style()
        self._build()
        if self.drop_supported:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self._on_drop)

    def t(self, key: str, **values) -> str:
        return tr(self.language, key, **values)

    def _configure_style(self):
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Exact.TLabel", foreground="#087f5b", font=("Segoe UI", 10, "bold"))
        style.configure("Structural.TLabel", foreground="#b05a00", font=("Segoe UI", 10, "bold"))

    def _build(self):
        self.root.title(self.t("title"))
        top = ttk.Frame(self.root, padding=16)
        top.pack(fill="x")
        title_row = ttk.Frame(top)
        title_row.pack(fill="x")
        ttk.Label(title_row, text=self.t("heading"), style="Title.TLabel").pack(side="left", anchor="w")
        ttk.Label(title_row, text=self.t("language")).pack(side="right", padx=(8, 0))
        language_var = tk.StringVar(value="English" if self.language == "en" else "Русский")
        language_box = ttk.Combobox(title_row, textvariable=language_var, values=("English", "Русский"), state="readonly", width=10)
        language_box.pack(side="right")
        language_box.bind("<<ComboboxSelected>>", lambda _e: self._change_language("en" if language_var.get() == "English" else "ru"))
        ttk.Label(top, text=self.t("subtitle")).pack(anchor="w", pady=(2, 12))
        firmware = ttk.LabelFrame(top, text=self.t("firmware"), padding=12)
        firmware.pack(fill="x")
        ttk.Button(firmware, text=self.t("open"), command=self.choose_file).pack(side="left")
        if self.drop_supported:
            ttk.Label(firmware, text=self.t("drop")).pack(side="left", padx=12)
        self.file_label = ttk.Label(firmware, text=self.t("no_file"))
        self.file_label.pack(side="right")

        self.status = tk.StringVar(value=self.t("ready"))
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w", padding=5).pack(side="bottom", fill="x")
        action_bar = ttk.Frame(self.root, padding=(16, 8))
        action_bar.pack(side="bottom", fill="x")
        template_row = ttk.Frame(action_bar)
        template_row.pack(fill="x", pady=(0, 7))
        ttk.Label(template_row, text=self.t("ota_template"), style="Heading.TLabel").pack(side="left")
        self.template_label = ttk.Label(template_row, text="—")
        self.template_label.pack(side="left", padx=6)
        self.choose_template_button = ttk.Button(template_row, text=self.t("choose_template"), command=self.choose_template, state="disabled")
        self.choose_template_button.pack(side="right")
        self.reset_template_button = ttk.Button(template_row, text=self.t("reset_template"), command=self.reset_template, state="disabled")
        self.reset_template_button.pack(side="right", padx=6)
        self.template_help = ttk.Label(action_bar, text=self.t("template_help"), foreground="#666")
        self.template_help.pack(anchor="w", pady=(0, 7))
        button_row = ttk.Frame(action_bar)
        button_row.pack(fill="x")
        self.reset_button = ttk.Button(button_row, text=self.t("reset_values"), command=self._populate_editor, state="disabled")
        self.reset_button.pack(side="left")
        self.ota_button = ttk.Button(button_row, text=self.t("export_ota"), command=self.export_ota, state="disabled")
        self.ota_button.pack(side="right")
        self.raw_button = ttk.Button(button_row, text=self.t("export_raw"), command=self.export_raw, state="disabled")
        self.raw_button.pack(side="right", padx=8)

        self.canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, padding=(16, 0, 16, 16))
        self.body_window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.body_window, width=e.width))
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.info = ttk.LabelFrame(self.body, text=self.t("recognition"), padding=12)
        self.info.pack(fill="x", pady=(0, 10))
        self.profile_label = ttk.Label(self.info, text=self.t("open_firmware"))
        self.profile_label.pack(anchor="w")
        self.hash_label = ttk.Label(self.info, text="", font=("Consolas", 9))
        self.hash_label.pack(anchor="w")
        self.trust_label = ttk.Label(self.info, text="")
        self.trust_label.pack(anchor="w", pady=(4, 0))
        self.editor = ttk.Frame(self.body)
        self.editor.pack(fill="both", expand=True)

    def _change_language(self, language: str):
        if language == self.language:
            return
        pair_drafts = {key: (values[0].get(), values[1].get()) for key, values in self.pair_vars.items()}
        scalar_drafts = {key: value.get() for key, value in self.scalar_vars.items()}
        self.language = language
        save_language(language)
        for child in self.root.winfo_children():
            child.destroy()
        self._build()
        if self.document:
            self._show_document()
            self._populate_editor()
            for key, values in pair_drafts.items():
                if key in self.pair_vars:
                    self.pair_vars[key][0].set(values[0])
                    self.pair_vars[key][1].set(values[1])
            for key, value in scalar_drafts.items():
                if key in self.scalar_vars:
                    self.scalar_vars[key].set(value)
            self.status.set(self.t("loaded_readonly" if self.document.read_only else "loaded"))

    def choose_file(self):
        path = filedialog.askopenfilename(title=self.t("open"), filetypes=[("VCU firmware", "*.bin *.zip"), ("All files", "*.*")])
        if path:
            self.load_path(path)

    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if paths:
            self.load_path(paths[0])

    def load_path(self, path: str):
        self.status.set(self.t("checking"))
        self.root.update_idletasks()
        try:
            document = FirmwareDocument.open(path)
        except Exception as exc:
            error = localize_error(str(exc), self.language)
            self.document = None
            self.custom_template = None
            self._clear_editor()
            self.file_label.configure(text=Path(path).name)
            self.profile_label.configure(text=self.t("write_blocked"))
            self.hash_label.configure(text="")
            self.trust_label.configure(text=error, style="Structural.TLabel")
            self._set_actions(False)
            self.status.set(self.t("rejected"))
            messagebox.showerror(self.t("unsupported_title"), error)
            return
        self.document = document
        self.custom_template = None
        self._show_document()
        self._populate_editor()
        self.status.set(self.t("loaded_readonly" if document.read_only else "loaded"))

    def _show_document(self):
        assert self.document
        document = self.document
        self.file_label.configure(text=document.path.name)
        self.profile_label.configure(text=f"VCU {document.profile.version} · {document.container} · {len(document.raw)} bytes")
        self.hash_label.configure(text="SHA-256: " + document.digest)
        style = "Exact.TLabel" if document.trust == "exact" else "Structural.TLabel"
        trust_key = "readonly" if document.read_only else document.trust
        self.trust_label.configure(text=self.t(trust_key), style=style)
        self._set_actions(not document.read_only)
        if not document.read_only:
            self._update_template_label()

    def _set_actions(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for button in (self.reset_button, self.raw_button, self.ota_button, self.choose_template_button):
            button.configure(state=state)
        self.reset_template_button.configure(state=state if enabled and self.custom_template else "disabled")
        if not enabled:
            self.template_label.configure(text="—")

    def _clear_editor(self):
        for child in self.editor.winfo_children():
            child.destroy()
        self.pair_vars.clear()
        self.scalar_vars.clear()

    def _pair_label(self, key: str) -> str:
        if key.startswith("mode_"):
            return self.t(key[5:])
        if key.startswith("preset_"):
            return self.t("sport_preset", value=key[-1])
        return key

    def _populate_editor(self):
        if not self.document:
            return
        self._clear_editor()
        pair_box = ttk.LabelFrame(self.editor, text=self.t("pair_box"), padding=12)
        pair_box.pack(fill="x", pady=(0, 10))
        for column, label in enumerate((self.t("profile_mode"), "A0 raw (u16)", "A1 raw (u8)", self.t("storage"))):
            ttk.Label(pair_box, text=label, style="Heading.TLabel").grid(row=0, column=column, sticky="w", padx=(0, 8))
        row = 0
        for row, item in enumerate(self.document.pairs(), 1):
            label = self.t("sport_working") if not item.editable and item.key == "mode_sport" else self._pair_label(item.key)
            ttk.Label(pair_box, text=label).grid(row=row, column=0, sticky="w", pady=3)
            a0_var, a1_var = tk.StringVar(value=str(item.a0)), tk.StringVar(value=str(item.a1))
            self.pair_vars[item.key] = (a0_var, a1_var)
            state = "normal" if item.editable else "disabled"
            ttk.Entry(pair_box, textvariable=a0_var, width=12, state=state).grid(row=row, column=1, padx=8)
            ttk.Entry(pair_box, textvariable=a1_var, width=12, state=state).grid(row=row, column=2, padx=8)
            suffix = "" if item.editable else " · " + self.t("read_only")
            ttk.Label(pair_box, text=f"{item.location}{suffix}").grid(row=row, column=3, sticky="w")
        pair_note = "readonly_pair_note" if self.document.read_only else "pair_note"
        ttk.Label(pair_box, text=self.t(pair_note), foreground="#555").grid(row=row + 1, column=0, columnspan=4, sticky="w", pady=(8, 0))

        scalar_box = ttk.LabelFrame(self.editor, text=self.t("scalar_box"), padding=12)
        scalar_box.pack(fill="x", pady=(0, 10))
        for column, label in enumerate((self.t("field"), self.t("value"), self.t("scope_location"))):
            ttk.Label(scalar_box, text=label, style="Heading.TLabel").grid(row=0, column=column, sticky="w", padx=(0, 8))
        labels = {"a2": "a2", "a3_1": "a3_1", "a3_2": "a3_2", "a4": "a4", "drive": "drive_speed", "sport_fallback": "sport_fallback"}
        scopes = {"a2": "scope_a2", "a3_1": "scope_a3", "a3_2": "scope_a3", "a4": "scope_a4", "drive": "scope_drive", "sport_fallback": "scope_sport"}
        scalars = self.document.scalars()
        for row, item in enumerate(scalars, 1):
            ttk.Label(scalar_box, text=self.t(labels[item.key])).grid(row=row, column=0, sticky="w", pady=3)
            variable = tk.StringVar(value=str(item.value))
            self.scalar_vars[item.key] = variable
            ttk.Entry(scalar_box, textvariable=variable, width=12, state="normal" if item.editable else "disabled").grid(row=row, column=1, padx=8)
            ttk.Label(scalar_box, text=f"{self.t(scopes[item.key])} · {item.location}").grid(row=row, column=2, sticky="w")
        count = sum(encode_thumb_imm(value << 8) is not None for value in range(256))
        scalar_note = "readonly_scalar_note" if self.document.read_only else "scalar_note"
        ttk.Label(scalar_box, text=self.t(scalar_note, count=count), foreground="#555").grid(row=len(scalars) + 1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        warning = ttk.LabelFrame(self.editor, text=self.t("safety"), padding=12)
        warning.pack(fill="x", pady=(0, 10))
        safety_note = "readonly_safety_note" if self.document.read_only else "safety_note"
        ttk.Label(warning, text=self.t(safety_note), foreground="#7a3e00").pack(anchor="w")

    def _default_stem(self) -> str:
        assert self.document
        return default_output_stem(self.document)

    def choose_template(self):
        path = filedialog.askopenfilename(title=self.t("select_template"), filetypes=[("OTA ZIP", "*.zip"), ("All files", "*.*")])
        if path:
            try:
                validate_ota_template(path)
            except FirmwareError as exc:
                messagebox.showerror(self.t("export_failed"), localize_error(str(exc), self.language))
            else:
                self.custom_template = Path(path)
                self._update_template_label()

    def reset_template(self):
        self.custom_template = None
        self._update_template_label()

    def _update_template_label(self):
        if not self.document:
            return
        if self.custom_template:
            text = self.t("custom_template", name=self.custom_template.name)
        elif self.document.ota_entries:
            text = self.t("loaded_ota_template", name=self.document.path.name)
        else:
            details = bundled_template_details()
            text = self.t("bundled_template", name=details["display_name"], digest=details["sha256"][:12] + "…")
        self.template_label.configure(text=text)
        self.reset_template_button.configure(state="normal" if self.custom_template else "disabled")

    def _collect(self):
        assert self.document
        editable_pairs = {item.key for item in self.document.pairs() if item.editable}
        editable_scalars = {item.key for item in self.document.scalars() if item.editable}
        try:
            pairs = {key: (int(values[0].get(), 10), int(values[1].get(), 10)) for key, values in self.pair_vars.items() if key in editable_pairs}
            scalars = {key: int(value.get(), 10) for key, value in self.scalar_vars.items() if key in editable_scalars}
            return pairs, scalars
        except ValueError as exc:
            raise FirmwareError(self.t("integers")) from exc

    def export_raw(self):
        if not self.document:
            return
        output = filedialog.asksaveasfilename(title=self.t("save_raw"), initialfile=self._default_stem() + ".bin", defaultextension=".bin", filetypes=[("Raw firmware", "*.bin")])
        if output:
            self._run_export("raw", output)

    def export_ota(self):
        if not self.document:
            return
        output = filedialog.asksaveasfilename(title=self.t("save_ota"), initialfile=self._default_stem() + "_OTA.zip", defaultextension=".zip", filetypes=[("OTA ZIP", "*.zip")])
        if output:
            self._run_export("ota", output)

    def _run_export(self, kind: str, output: str):
        assert self.document
        try:
            pairs, scalars = self._collect()
            self.status.set(self.t("exporting"))
            self.root.update_idletasks()
            if kind == "raw":
                artifact, audit = self.document.export_raw(output, pairs, scalars)
            else:
                artifact, audit = self.document.export_ota(output, pairs, scalars, self.custom_template)
        except Exception as exc:
            error = localize_error(str(exc), self.language)
            self.status.set(self.t("export_rejected"))
            messagebox.showerror(self.t("export_failed"), error)
            return
        self.status.set(self.t("done", name=artifact.name))
        messagebox.showinfo(self.t("export_complete"), self.t("created", artifact=artifact, audit=audit))


def main(initial_path: str | None = None):
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    app = TunerApp(root)
    if initial_path:
        root.after_idle(lambda: app.load_path(initial_path))
    root.mainloop()
