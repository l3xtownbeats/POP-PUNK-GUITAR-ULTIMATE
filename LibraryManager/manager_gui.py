#!/usr/bin/env python3
"""Portable Tkinter front end for POP PUNK GUITAR Library Manager.

Uses only Python's standard library plus the existing LibraryManager modules.
All file operations remain review-gated by library_operations.py.
"""
from __future__ import annotations

import json
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from unified_manager import run_manager
from library_operations import (
    cleanup_original_sources,
    distribute_assets,
    distribution_plan,
)

APP_VERSION = "1.6.0"
MANAGER_DIR = Path(__file__).resolve().parent
DEFAULT_SAMPLES = MANAGER_DIR.parent / "Samples"
STAGING_ROOT = MANAGER_DIR / "staging"


class LibraryManagerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"POP PUNK GUITAR LIBRARY MANAGER {APP_VERSION}")
        self.root.geometry("980x680")
        self.root.minsize(760, 520)
        self.samples_root = tk.StringVar(value=str(DEFAULT_SAMPLES))
        self.analyze_audio = tk.BooleanVar(value=True)
        self.guitar_confirmed = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Готов. Выберите папку Samples и запустите анализ.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="POP PUNK GUITAR LIBRARY MANAGER",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text=f"Portable Library Manager • v{APP_VERSION}").pack(anchor="w", pady=(0, 10))

        path_row = ttk.Frame(outer)
        path_row.pack(fill="x", pady=4)
        ttk.Label(path_row, text="Папка Samples:").pack(side="left")
        ttk.Entry(path_row, textvariable=self.samples_root).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(path_row, text="Обзор…", command=self.choose_samples).pack(side="right")

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=6)
        ttk.Checkbutton(options, text="Акустический и ритмический анализ WAV",
                        variable=self.analyze_audio).pack(side="left")
        ttk.Checkbutton(options, text="Подтверждаю, что входные файлы — гитарный материал",
                        variable=self.guitar_confirmed).pack(side="left", padx=16)

        actions = ttk.LabelFrame(outer, text="Рабочие операции", padding=8)
        actions.pack(fill="x", pady=8)
        buttons = [
            ("1. Анализ библиотеки", self.scan),
            ("2. Распределить проверенные материалы", self.distribute),
            ("3. Удалить оригиналы после проверки", self.cleanup),
            ("Открыть отчёты", self.open_reports),
            ("Открыть staging", self.open_staging),
        ]
        for label, command in buttons:
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=4, pady=3)

        ttk.Label(outer, text="Журнал работы:").pack(anchor="w", pady=(8, 2))
        self.log = tk.Text(outer, wrap="word", height=22, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        ttk.Label(outer, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", pady=(8, 0))

        self._write("Менеджер не перемещает и не удаляет исходники при анализе.\n"
                    "FACTORY принимает только REVIEWED + LICENSE_APPROVED WAV.\n"
                    "Кандидаты и неподтверждённые материалы остаются в staging/Import Sample Guitar.\n")

    def _write(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _samples(self) -> Path:
        path = Path(self.samples_root.get()).expanduser()
        if not path.is_dir():
            raise FileNotFoundError(f"Папка Samples не найдена: {path}")
        if not (path / "Import Sample Guitar").is_dir():
            raise FileNotFoundError("В выбранной папке нет Import Sample Guitar.")
        return path.resolve()

    def choose_samples(self) -> None:
        selected = filedialog.askdirectory(title="Выберите корневую папку Samples")
        if selected:
            self.samples_root.set(selected)

    def _background(self, title: str, work) -> None:
        self.status.set(title + "…")
        def runner():
            try:
                result = work()
                self.root.after(0, lambda: self._finish(title, result))
            except Exception as exc:
                details = traceback.format_exc()
                self.root.after(0, lambda error=exc, trace=details: self._error(title, error, trace))
        threading.Thread(target=runner, daemon=True).start()

    def _finish(self, title: str, result) -> None:
        self._write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        self.status.set(title + ": завершено")

    def _error(self, title: str, exc: Exception, details: str) -> None:
        self._write(details)
        self.status.set(title + ": ошибка")
        messagebox.showerror("Ошибка", f"{type(exc).__name__}: {exc}")

    def scan(self) -> None:
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        analyze_audio = self.analyze_audio.get()
        guitar_confirmed = self.guitar_confirmed.get()
        def work():
            return run_manager(
                samples,
                analyze_audio=analyze_audio,
                guitar_source_confirmed=guitar_confirmed,
                write_virtual=False,
            )
        self._background("Анализ библиотеки", work)

    def distribute(self) -> None:
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        selected = filedialog.askopenfilenames(
            title="Выберите проверенные JSON-манифесты из LibraryManager/staging",
            initialdir=str(STAGING_ROOT),
            filetypes=[("JSON manifests", "*.json")],
        )
        if not selected:
            return
        manifests = [Path(item) for item in selected]
        try:
            plan = distribution_plan(manifests, samples, STAGING_ROOT)
        except Exception as exc:
            messagebox.showerror("План распределения", str(exc))
            return
        preview = "\n".join(
            f'{entry["category_path"]}\n  {entry["source_path"]}\n  → {entry["destination_path"]}'
            for entry in plan["entries"]
        )
        self._write("ПЛАН РАСПРЕДЕЛЕНИЯ (пока без изменений):\n" + preview)
        if not messagebox.askyesno(
            "Подтверждение копирования",
            f"Будет скопировано файлов: {len(plan['entries'])}.\n"
            "Каждый файл и манифест прошёл проверку review/license/SHA-256.\n"
            "Оригиналы останутся на месте.\n\nВыполнить копирование в FACTORY?"
        ):
            self.status.set("Распределение отменено пользователем")
            return
        self._background("Распределение FACTORY", lambda: distribute_assets(
            plan, approve=True,
            journal_path=samples / "FACTORY" / "LibraryManagerReports" / "operations.jsonl",
        ))

    def cleanup(self) -> None:
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        selected = filedialog.askopenfilenames(
            title="Выберите распределённые sidecar-манифесты из FACTORY",
            initialdir=str(samples / "FACTORY"),
            filetypes=[("Distributed asset manifests", "*.wav.json"), ("JSON", "*.json")],
        )
        if not selected:
            return
        if not messagebox.askyesno(
            "Удаление оригиналов — подтверждение 1/2",
            "Удалить исходные записи, от которых получены выбранные материалы?\n"
            "Перед удалением будут повторно проверены SHA-256 всех оригиналов и копий."
        ):
            return
        if not messagebox.askyesno(
            "Удаление оригиналов — подтверждение 2/2",
            "Подтверждаете, что выбраны ВСЕ зависимые фрагменты для каждого исходника "
            "и других нужных производных материалов не осталось?"
        ):
            return
        def work():
            return cleanup_original_sources(
                [Path(item) for item in selected],
                samples_root=samples,
                confirm_delete=True,
                confirm_all_dependents_accounted_for=True,
                journal_path=samples / "FACTORY" / "LibraryManagerReports" / "operations.jsonl",
            )
        self._background("Очистка исходников", work)

    def open_reports(self) -> None:
        path = MANAGER_DIR / "reports"
        path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def open_staging(self) -> None:
        STAGING_ROOT.mkdir(parents=True, exist_ok=True)
        self._open_path(STAGING_ROOT)

    @staticmethod
    def _open_path(path: Path) -> None:
        import os
        import subprocess
        if os.name == "nt":
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)])


def main() -> int:
    root = tk.Tk()
    LibraryManagerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
