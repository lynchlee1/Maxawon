import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

try:
    import ttkbootstrap as ttk
except ImportError as exc:  # pragma: no cover - import guard for CLI-only envs
    ttk = None
    TTKBOOTSTRAP_IMPORT_ERROR = exc
else:
    TTKBOOTSTRAP_IMPORT_ERROR = None

from weekly_mezz.cli import collect_and_export, default_date_range, format_yyyymmdd, parse_yyyymmdd
from weekly_mezz.export import default_output_path
from weekly_mezz.settings import get_api_key, get_config_value, save_api_key, set_config_value


class MezzanineCollectorApp:
    BG = "#F4F6F8"
    PANEL = "#FFFFFF"
    TEXT = "#111827"
    MUTED = "#64748B"

    def __init__(self):
        if ttk is None:
            raise RuntimeError("ttkbootstrap is not installed.") from TTKBOOTSTRAP_IMPORT_ERROR

        self.root = ttk.Window(themename="flatly")
        self.root.title("Weekly Mezzanine")
        self.root.geometry("980x1120")
        self.root.resizable(False, False)

        self.worker = None
        self.stop_requested = False
        self.log_queue = queue.Queue()
        self.last_output_path = None

        self._build_vars()
        self._build_layout()
        self._poll_logs()

    def _build_vars(self):
        default_start, default_end = default_date_range()
        self.api_key_var = tk.StringVar(value=get_api_key(""))
        self.start_date_var = tk.StringVar(value=get_config_value("start_date", format_yyyymmdd(default_start)))
        self.end_date_var = tk.StringVar(value=get_config_value("end_date", format_yyyymmdd(default_end)))
        self.output_path_var = tk.StringVar(value=get_config_value("output_path", str(default_output_path())))
        self.last_reprt_at_var = tk.StringVar(value=get_config_value("last_reprt_at", "N"))
        self.final_reports_var = tk.BooleanVar(value=self.last_reprt_at_var.get() == "Y")

    def _build_layout(self):
        self.root.configure(bg=self.BG)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        header = tk.Frame(self.root, bg=self.BG, padx=24, pady=22)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="WEEKLY MEZZANINE",
            font=("Arial", 19, "bold"),
            fg=self.TEXT,
            bg=self.BG,
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="KIND disclosure collector / OpenDART parser",
            font=("Arial", 12),
            fg=self.MUTED,
            bg=self.BG,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        settings = ttk.Labelframe(self.root, text="Settings", padding=22, bootstyle="secondary")
        settings.grid(row=1, column=0, sticky="ew", padx=24, pady=(18, 16))
        settings.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="settings")

        self._add_entry(settings, "OPENDART API KEY", self.api_key_var, 0, 0, columnspan=2)
        self._add_entry(settings, "시작일", self.start_date_var, 1, 0)
        self._add_entry(settings, "종료일", self.end_date_var, 1, 1)
        self._add_entry(settings, "저장 경로", self.output_path_var, 2, 0, browse=self.choose_output, columnspan=3)

        final_box = ttk.Frame(settings)
        final_box.grid(row=2, column=3, sticky="nw", padx=(18, 0), pady=(14, 0))
        ttk.Label(final_box, text="최종보고서만 보기", font=("Malgun Gothic", 11, "bold"), foreground=self.MUTED).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )
        ttk.Checkbutton(
            final_box,
            text="사용",
            variable=self.final_reports_var,
            command=self._set_last_report_value,
            bootstyle="round-toggle",
        ).grid(row=1, column=0, sticky="w")

        button_row = ttk.Frame(settings)
        button_row.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(24, 0))
        button_row.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="buttons")
        self.run_button = ttk.Button(button_row, text="RUN", command=self.run_collection, bootstyle="success")
        self.run_button.grid(row=0, column=0, sticky="ew", padx=(0, 10), ipady=8)
        self.stop_button = ttk.Button(button_row, text="STOP", command=self.request_stop, bootstyle="secondary-outline")
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=10, ipady=8)
        ttk.Button(button_row, text="SAVE SETTINGS", command=self.save_settings, bootstyle="secondary-outline").grid(
            row=0,
            column=2,
            sticky="ew",
            padx=10,
            ipady=8,
        )
        ttk.Button(button_row, text="OPEN RESULT", command=self.open_result, bootstyle="secondary-outline").grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(10, 0),
            ipady=8,
        )

        main = ttk.Frame(self.root)
        main.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            main,
            bg="#FAFBFC",
            fg=self.TEXT,
            relief="solid",
            bd=1,
            font=("Consolas", 12),
            wrap="word",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.insert("end", "Ready.\n")
        self.log_text.configure(state="disabled")

    def _add_entry(self, parent, label, variable, row, column, browse=None, columnspan=1):
        group = ttk.Frame(parent)
        group.grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=(0, 18), pady=(14, 0))
        group.grid_columnconfigure(0, weight=1)

        ttk.Label(group, text=label, font=("Malgun Gothic", 11, "bold"), foreground=self.MUTED).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )
        entry_row = ttk.Frame(group)
        entry_row.grid(row=1, column=0, sticky="ew")
        entry_row.grid_columnconfigure(0, weight=1)

        ttk.Entry(entry_row, textvariable=variable, font=("Arial", 11)).grid(row=0, column=0, sticky="ew", ipady=5)
        if browse:
            ttk.Button(entry_row, text="...", width=4, command=browse, bootstyle="secondary-outline").grid(
                row=0,
                column=1,
                padx=(10, 0),
                ipady=5,
            )

    def _set_last_report_value(self):
        self.last_reprt_at_var.set("Y" if self.final_reports_var.get() else "N")

    def save_settings(self):
        self._set_last_report_value()
        save_api_key(self.api_key_var.get())
        set_config_value("start_date", self.start_date_var.get())
        set_config_value("end_date", self.end_date_var.get())
        set_config_value("output_path", self.output_path_var.get())
        set_config_value("last_reprt_at", self.last_reprt_at_var.get())
        self._append_log("Settings saved.")

    def choose_output(self):
        path = filedialog.asksaveasfilename(
            title="Save XLSX",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=Path(self.output_path_var.get() or "mezzanine_reports.xlsx").name,
        )
        if path:
            self.output_path_var.set(path)

    def run_collection(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Weekly Mezzanine", "Already running.")
            return
        try:
            start_date = parse_yyyymmdd(self.start_date_var.get())
            end_date = parse_yyyymmdd(self.end_date_var.get())
        except ValueError:
            messagebox.showerror("Weekly Mezzanine", "Dates must use YYYYMMDD format.")
            return
        if not self.api_key_var.get().strip():
            messagebox.showerror("Weekly Mezzanine", "Enter an OpenDART API Key.")
            return

        self.save_settings()
        self.stop_requested = False
        self.worker = threading.Thread(
            target=self._run_worker,
            args=(start_date, end_date),
            daemon=True,
        )
        self.worker.start()

    def _run_worker(self, start_date, end_date):
        try:
            result = collect_and_export(
                start_date,
                end_date,
                self.output_path_var.get(),
                api_key=self.api_key_var.get(),
                last_reprt_at=self.last_reprt_at_var.get(),
                progress_callback=self._progress_callback,
            )
            self.last_output_path = result.output_path
            self._queue_log(f"Saved XLSX: {result.output_path}")
        except Exception as exc:
            self._queue_log(f"ERROR: {exc}")

    def request_stop(self):
        self.stop_requested = True
        self._append_log("Stop requested. Current network request may finish first.")

    def open_result(self):
        path = self.last_output_path or Path(self.output_path_var.get()).expanduser()
        if not path.exists():
            messagebox.showinfo("Weekly Mezzanine", "No result file is available.")
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["cmd", "/c", "start", "", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _queue_log(self, message):
        self.log_queue.put(("log", message))

    def _progress_callback(self, message):
        if self.stop_requested:
            raise RuntimeError("The user requested a stop.")
        self._queue_log(message)

    def _append_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_logs(self):
        while True:
            try:
                kind, payload = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(payload)
        self.root.after(150, self._poll_logs)

    def run(self):
        self.root.mainloop()


def main():
    MezzanineCollectorApp().run()


if __name__ == "__main__":
    main()
