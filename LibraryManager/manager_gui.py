#!/usr/bin/env python3
"""Portable Tkinter front end for POP PUNK GUITAR Library Manager.

Uses only Python's standard library plus the existing LibraryManager modules.
All file operations remain review-gated by library_operations.py.
"""
from __future__ import annotations

import json
import queue
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path

from unified_manager import run_manager, quick_scan, resolve_samples_root
from pattern_clip_extractor import extract_pattern_occurrences
from other_audit import audit_other_library, route_approved_to_other
from cleanup_audit import audit_all_import_sources, cleanup_sources_from_audit
from finalization import finalize_library as finalize_library_audit
from manifest_review import review_manifest
from library_operations import (
    cleanup_original_sources,
    distribute_assets,
    distribution_plan,
)

APP_VERSION = "2.1.0"
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
        self.status = tk.StringVar(value="Готов. Выберите Samples или непосредственно Import Sample Guitar.")
        # Worker threads must never call Tkinter methods. They only enqueue events;
        # the Tk main thread drains this queue in _poll_worker_events().
        self._worker_events = queue.Queue()
        self._job_running = False
        self._worker_thread = None
        self._cancel_event = threading.Event()
        self._action_buttons = []
        self._cancel_button = None
        self._build()
        self.root.after(100, self._poll_worker_events)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="POP PUNK GUITAR LIBRARY MANAGER",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text=f"Portable Library Manager • v{APP_VERSION}").pack(anchor="w", pady=(0, 10))

        path_row = ttk.Frame(outer)
        path_row.pack(fill="x", pady=4)
        ttk.Label(path_row, text="Папка Samples / Import Sample Guitar:").pack(side="left")
        ttk.Entry(path_row, textvariable=self.samples_root).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(path_row, text="Обзор…", command=self.choose_samples).pack(side="right")

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=6)
        ttk.Checkbutton(options, text="Акустический и ритмический анализ аудиофайлов",
                        variable=self.analyze_audio).pack(side="left")
        ttk.Checkbutton(options, text="Подтверждаю, что входные файлы — гитарный материал",
                        variable=self.guitar_confirmed).pack(side="left", padx=16)

        actions = ttk.LabelFrame(outer, text="Рабочие операции", padding=8)
        actions.pack(fill="x", pady=8)
        buttons = [
            ("1. Быстрое сканирование", self.quick_scan_only),
            ("2. Полный цикл: анализ + извлечение", self.scan),
            ("Предпрослушать WAV", self.preview_audio),
            ("Остановить звук", self.stop_preview),
            ("Аудит папки OTHER", self.audit_other),
            ("Распределить одобренное в OTHER", self.distribute_other),
            ("Отдельное извлечение Pattern WAV", self.extract_patterns),
            ("3. Проверить WAV-кандидат", self.review_candidate),
            ("4. Финализировать staging + FACTORY", self.finalize_library),
            ("5. Распределить проверенные материалы", self.distribute),
            ("Полный аудит очистки Import", self.audit_cleanup),
            ("Удалить оригиналы после полного аудита", self.cleanup),
            ("Открыть отчёты", self.open_reports),
            ("Открыть staging", self.open_staging),
        ]
        for column in range(3):
            actions.columnconfigure(column, weight=1)
        for index, (label, command) in enumerate(buttons):
            button = ttk.Button(actions, text=label, command=command)
            button.grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=3)
            self._action_buttons.append(button)
        cancel_row = (len(buttons) + 2) // 3
        self._cancel_button = ttk.Button(actions, text="ОСТАНОВИТЬ задачу", command=self.cancel_job, state="disabled")
        self._cancel_button.grid(row=cancel_row, column=0, columnspan=3, sticky="ew", padx=4, pady=5)

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
        """Resolve and log the exact Samples/Import Sample Guitar paths."""
        selected = Path(self.samples_root.get()).expanduser()
        resolved = resolve_samples_root(selected)
        incoming = next(
            p for p in resolved.iterdir()
            if p.is_dir() and p.name.strip().casefold() == "import sample guitar"
        )
        self._write(f"Путь Samples: {resolved}")
        self._write(f"Путь входной библиотеки: {incoming.resolve()}")
        return resolved

    def choose_samples(self) -> None:
        selected = filedialog.askdirectory(
            title="Выберите Samples ИЛИ непосредственно Import Sample Guitar"
        )
        if selected:
            self.samples_root.set(selected)

    def _background(self, title: str, work) -> None:
        """Run work off the UI thread and deliver all UI updates via a queue."""
        if self._job_running:
            self._write(f"[ОТКАЗ] Уже выполняется другая операция: {title}")
            self.status.set("Дождитесь завершения текущей операции.")
            return

        self._job_running = True
        self._cancel_event.clear()
        self._cancel_button.configure(state="normal")
        self.status.set(title + " — запуск…")
        for button in self._action_buttons:
            button.configure(state="disabled")
        self._write(f"[ЗАДАЧА] Запуск фонового потока: {title}")

        def runner():
            try:
                result = work()
                self._worker_events.put(("finish", title, result))
            except Exception as exc:
                self._worker_events.put(("error", title, f"{type(exc).__name__}: {exc}", traceback.format_exc()))

        worker = threading.Thread(target=runner, name="LibraryManagerWorker", daemon=True)
        self._worker_thread = worker
        try:
            worker.start()
        except Exception as exc:
            self._job_running = False
            self._worker_thread = None
            for button in self._action_buttons:
                button.configure(state="normal")
            details = traceback.format_exc()
            self._error(title, exc, details)

    def _poll_worker_events(self) -> None:
        """Process worker events only on Tk's main thread."""
        try:
            while True:
                event = self._worker_events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self._progress(event[1])
                elif kind == "finish":
                    _, title, result = event
                    self._job_running = False
                    self._worker_thread = None
                    self._cancel_button.configure(state="disabled")
                    for button in self._action_buttons:
                        button.configure(state="normal")
                    self._finish(title, result)
                elif kind == "error":
                    _, title, error_text, details = event
                    self._job_running = False
                    self._worker_thread = None
                    self._cancel_button.configure(state="disabled")
                    for button in self._action_buttons:
                        button.configure(state="normal")
                    self._write(f"[ОШИБКА] {error_text}")
                    self._write(details)
                    self.status.set(title + ": ошибка")
                    messagebox.showerror("Ошибка", error_text)
        except queue.Empty:
            pass
        finally:
            try:
                self.root.after(100, self._poll_worker_events)
            except tk.TclError:
                # Window is already closing.
                pass

    def _finish(self, title: str, result) -> None:
        self._write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        self.status.set(title + ": завершено")

    def _error(self, title: str, exc: Exception, details: str) -> None:
        self._write(details)
        self.status.set(title + ": ошибка")
        messagebox.showerror("Ошибка", f"{type(exc).__name__}: {exc}")

    def cancel_job(self) -> None:
        if self._job_running:
            self._cancel_event.set()
            self._cancel_button.configure(state="disabled")
            self.status.set("Остановка запрошена — завершаю текущий безопасный блок…")
            self._write("[ОТМЕНА] Запрошена остановка. Исходные файлы не затрагиваются.")

    def quick_scan_only(self) -> None:
        """Run only the fast filesystem inventory; never start deep analysis."""
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return

        def work():
            def report_progress(message: str) -> None:
                self._worker_events.put(("progress", message))
            return quick_scan(
                samples, progress=report_progress, cancel_event=self._cancel_event,
            )

        self._write("=== БЫСТРОЕ СКАНИРОВАНИЕ ===")
        self._write("Только обход Import Sample Guitar и чтение файловой метаинформации. SHA-256, декодирование и анализ не запускаются.")
        self._background("Быстрое сканирование", work)

    def scan(self) -> None:
        """Run the complete preparation pipeline after the fast scan."""
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        analyze_audio = self.analyze_audio.get()
        guitar_confirmed = self.guitar_confirmed.get()

        def work():
            def report_progress(message: str) -> None:
                self._worker_events.put(("progress", message))

            report_progress("ЭТАП 1/6: быстрое сканирование структуры — только файловая метаинформация.")
            quick_result = quick_scan(
                samples, progress=report_progress, cancel_event=self._cancel_event,
            )
            if self._cancel_event.is_set():
                raise RuntimeError("Полный цикл остановлен после быстрого сканирования.")
            report_progress("ЭТАП 2/6: глубокая инвентаризация, SHA-256 cache, форматы, дубликаты и SFZ.")
            analysis_result = run_manager(
                samples,
                analyze_audio=analyze_audio,
                guitar_source_confirmed=guitar_confirmed,
                write_virtual=bool(analyze_audio and guitar_confirmed),
                progress=report_progress,
                cancel_event=self._cancel_event,
                workers=2,
            )

            extracted_pattern = 0
            extracted_sample = 0
            extracted_melody = 0
            extraction_failures = []
            report_file = Path(analysis_result["report_directory"]) / "unified_audio_analysis.json"
            if analyze_audio and guitar_confirmed and report_file.is_file():
                records = json.loads(report_file.read_text(encoding="utf-8"))
                from pattern_clip_extractor import extract_pattern_occurrences
                from sample_melody_pipeline import prepare_sample_and_melody

                report_progress("ЭТАП 3/6: физическое извлечение повторяющихся ритм-паттернов в WAV.")
                for record in records:
                    if self._cancel_event.is_set():
                        raise RuntimeError("Извлечение остановлено; созданные staging-кандидаты сохранены.")
                    pattern_data = (record.get("pattern_analysis") or {}).get("pattern_analysis", {})
                    if not pattern_data.get("patterns"):
                        continue
                    try:
                        clips = extract_pattern_occurrences({
                            "source": record["source_path"],
                            "source_sha256": record["source_sha256"],
                            "pattern_analysis": pattern_data,
                        }, STAGING_ROOT, max_clips=max(0, min(100, 500 - extracted_pattern)))
                        extracted_pattern += len(clips)
                    except Exception as exc:
                        extraction_failures.append({
                            "source_path": record.get("source_path"),
                            "stage": "PATTERN_EXTRACTION",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                    if extracted_pattern >= 500:
                        break

                report_progress("ЭТАП 4/6: извлечение отдельных нот для SAMPLE MODE и фраз для MELODY MODE.")
                for record in records:
                    if self._cancel_event.is_set():
                        raise RuntimeError("Извлечение остановлено; созданные staging-кандидаты сохранены.")
                    if extracted_sample + extracted_melody >= 500:
                        break
                    source = Path(record.get("source_path", ""))
                    if source.suffix.lower() not in {".wav", ".wave"}:
                        continue
                    try:
                        remaining = max(1, 500 - extracted_sample - extracted_melody)
                        result = prepare_sample_and_melody(
                            source, STAGING_ROOT,
                            max_note_events=min(100, remaining),
                        )
                        extracted_sample += result["sample_mode_count"]
                        extracted_melody += result["melody_mode_count"]
                        if result["sample_mode_count"] + result["melody_mode_count"] == 0:
                            extraction_failures.append({
                                "source_path": str(source),
                                "stage": "SAMPLE_MELODY_EXTRACTION",
                                "error": "Не обнаружены надёжные кандидаты pitch-events; WAV не создан.",
                            })
                    except Exception as exc:
                        extraction_failures.append({
                            "source_path": str(source),
                            "stage": "SAMPLE_MELODY_EXTRACTION",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
            elif analyze_audio and not guitar_confirmed:
                extraction_failures.append({
                    "stage": "EXTRACTION_GATE",
                    "error": "Физическое извлечение пропущено: оператор не подтвердил гитарный источник.",
                })

            report_progress("ЭТАП 5/6: финальная проверка SHA-256, границ, PCM WAV, музыкального статуса и лицензии.")
            finalization_result = finalize_library_audit(
                samples, STAGING_ROOT,
                progress=report_progress,
                cancel_event=self._cancel_event,
            )
            report_progress("ЭТАП 6/6: проверены staging и FACTORY; исходники и готовые WAV не изменялись.")
            return {
                "quick_scan": quick_result,
                "deep_analysis": analysis_result,
                "physical_extraction": {
                    "pattern_mode_wav_count": extracted_pattern,
                    "sample_mode_wav_count": extracted_sample,
                    "melody_mode_wav_count": extracted_melody,
                    "total_new_wav_candidates": extracted_pattern + extracted_sample + extracted_melody,
                    "manifest_count_in_staging": finalization_result["staging"]["manifests_checked"],
                    "failures": extraction_failures,
                    "review_status": "NEEDS_MUSICAL_REVIEW",
                    "license_status": "UNREVIEWED",
                },
                "finalization": finalization_result,
                "source_files_modified": False,
                "source_files_moved_or_deleted": False,
            }

        self._write("=== ПОЛНЫЙ ЦИКЛ ПОДГОТОВКИ БИБЛИОТЕКИ ===")
        self._write("Быстрый scan → глубокая инвентаризация → анализ → физическое извлечение Pattern/Sample/Melody WAV → проверка staging.")
        self._write("Извлечение запускается только после ручного подтверждения гитарного источника. FACTORY остаётся защищённой review/license gate.")
        self._write(f"Акустический анализ: {'ВКЛЮЧЁН' if analyze_audio else 'ВЫКЛЮЧЕН'}")
        self._write(f"Гитарный источник подтверждён: {'ДА' if guitar_confirmed else 'НЕТ'}")
        self._background("Полный цикл подготовки библиотеки", work)

    def _progress(self, message: str) -> None:
        self._write("[ВЫПОЛНЯЕТСЯ] " + message)
        self.status.set(message)

    def preview_audio(self) -> None:
        selected = filedialog.askopenfilename(
            title="Выберите WAV для предпрослушивания",
            filetypes=[("WAV audio", "*.wav *.wave")],
        )
        if not selected:
            return
        try:
            import winsound
            winsound.PlaySound(selected, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self._write("Предпрослушивание: " + selected)
            self.status.set("Воспроизведение WAV")
        except Exception as exc:
            messagebox.showerror("Предпрослушивание", f"Не удалось воспроизвести WAV: {exc}")

    def stop_preview(self) -> None:
        try:
            import winsound
            winsound.PlaySound(None, 0)
            self.status.set("Воспроизведение остановлено")
        except Exception as exc:
            messagebox.showerror("Предпрослушивание", str(exc))

    def audit_other(self) -> None:
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        report_dir = MANAGER_DIR / "reports" / ("other_audit_" + __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S"))
        self._background("Аудит OTHER", lambda: audit_other_library(samples, report_dir))

    def distribute_other(self) -> None:
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        decision_file = filedialog.askopenfilename(
            title="Выберите вручную проверенный other_decisions.json",
            initialdir=str(samples / "OTHER"),
            filetypes=[("OTHER decisions", "*.json")],
        )
        if not decision_file:
            return
        try:
            plan = route_approved_to_other(samples, Path(decision_file), approve=False)
        except Exception as exc:
            messagebox.showerror("План OTHER", str(exc))
            return
        preview = "\n".join(f'{item["source_path"]} → {item["destination_path"]} ({item["reason"]})' for item in plan["entries"])
        self._write("ПЛАН OTHER (без изменений):\n" + (preview or "Нет явно одобренных записей."))
        if not plan["entries"]:
            return
        if not messagebox.askyesno("Подтверждение копирования в OTHER",
                                   f"Будет скопировано файлов: {len(plan['entries'])}.\nSHA-256 проверяется; оригиналы останутся на месте. Продолжить?"):
            return
        self._background("Копирование в OTHER", lambda: route_approved_to_other(
            samples, Path(decision_file), approve=True))

    def extract_patterns(self) -> None:
        report_path = filedialog.askopenfilename(
            title="Выберите unified_audio_analysis.json из отчёта анализа",
            initialdir=str(MANAGER_DIR / "reports"),
            filetypes=[("Audio analysis report", "unified_audio_analysis.json"), ("JSON", "*.json")],
        )
        if not report_path:
            return
        try:
            records = json.loads(Path(report_path).read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError("Ожидается список аудио-отчётов.")
            eligible = [
                item for item in records
                if (item.get("pattern_analysis") or {}).get("pattern_analysis", {}).get("patterns")
            ]
            if not eligible:
                messagebox.showinfo("Паттерны не найдены",
                                    "В отчёте нет повторяющихся ритмических кандидатов для извлечения.")
                return
            total = sum(
                len(item["pattern_analysis"]["pattern_analysis"]["patterns"])
                for item in eligible
            )
            if not messagebox.askyesno(
                "Физическое извлечение WAV",
                f"Найдено исходных файлов с кандидатами: {len(eligible)}.\n"
                f"Кандидатов паттернов: {total}.\n"
                "Будут созданы отдельные WAV-фрагменты в LibraryManager/staging/clips "
                "и JSON-манифесты в staging/manifests.\n"
                "Все фрагменты останутся NEEDS_MUSICAL_REVIEW и UNREVIEWED.\n"
                "Продолжить?"
            ):
                return
        except Exception as exc:
            messagebox.showerror("Отчёт анализа", str(exc))
            return

        def work():
            extracted = []
            failures = []
            for item in eligible:
                pattern_report = {
                    "source": item["source_path"],
                    "source_sha256": item["source_sha256"],
                    "pattern_analysis": (item.get("pattern_analysis") or {}).get("pattern_analysis", {}),
                }
                try:
                    extracted.extend(extract_pattern_occurrences(pattern_report, STAGING_ROOT))
                except Exception as exc:
                    failures.append({
                        "source_path": item.get("source_path"),
                        "error": f"{type(exc).__name__}: {exc}",
                    })
            return {
                "extracted_count": len(extracted),
                "assets": extracted,
                "failures": failures,
                "review_required": True,
                "license_review_required": True,
            }
        self._background("Извлечение ритм-паттернов", work)

    def review_candidate(self) -> None:
        """Collect explicit musical and license decisions for one staged WAV."""
        selected = filedialog.askopenfilename(
            title="Выберите WAV-манифест для музыкальной и лицензионной проверки",
            initialdir=str(STAGING_ROOT / "manifests"),
            filetypes=[("Staging manifests", "*.json")],
        )
        if not selected:
            return
        from factory_curator import INSTRUMENTS, ROLES, STYLES, TONES

        def ask_value(title: str, prompt: str, values: set[str]) -> str | None:
            return simpledialog.askstring(
                title, prompt + "\n\nДопустимые значения:\n" + ", ".join(sorted(values)),
                parent=self.root,
            )

        style = ask_value("Стиль", "Укажите подтверждённый стиль:", STYLES)
        if style is None:
            return
        instrument = ask_value("Инструмент", "Укажите подтверждённое семейство инструмента:", INSTRUMENTS)
        if instrument is None:
            return
        role = ask_value("Тип материала", "Укажите подтверждённую роль материала:", ROLES)
        if role is None:
            return
        tone = ask_value("Характер звучания", "Укажите подтверждённый тип звучания:", TONES)
        if tone is None:
            return
        notes = simpledialog.askstring(
            "Музыкальная проверка",
            "Что прослушано и проверено? Укажите границы, характер партии и возможные ограничения:",
            parent=self.root,
        )
        if notes is None:
            return
        evidence = simpledialog.askstring(
            "Лицензионное основание",
            "Укажите лицензию/источник и основание, разрешающее включение производного WAV в распространяемую FACTORY-библиотеку:",
            parent=self.root,
        )
        if evidence is None:
            return
        if not messagebox.askyesno(
            "Подтверждение REVIEWED",
            "Подтверждаете, что лично прослушали WAV и проверили музыкальное содержимое и границы?",
            parent=self.root,
        ):
            return
        if not messagebox.askyesno(
            "Подтверждение LICENSE_APPROVED",
            "Подтверждаете, что указанное лицензионное основание действительно разрешает распространение этого материала?",
            parent=self.root,
        ):
            return

        def work():
            return review_manifest(
                Path(selected), STAGING_ROOT,
                style_family=style.strip().upper(),
                instrument_family=instrument.strip().upper(),
                asset_role=role.strip().upper(),
                tone_family=tone.strip().upper(),
                musical_review_notes=notes,
                license_evidence=evidence,
                approve_musical_review=True,
                approve_license=True,
            )
        self._background("Музыкальная и лицензионная проверка WAV", work)

    def finalize_library(self) -> None:
        """Audit staging and distributed Factory without moving or copying assets."""
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        def progress(message: str) -> None:
            self._worker_events.put(("progress", message))
        self._background(
            "Финализация библиотеки",
            lambda: finalize_library_audit(
                samples, STAGING_ROOT,
                progress=progress,
                cancel_event=self._cancel_event,
            ),
        )

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

    def audit_cleanup(self) -> None:
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        report_path = MANAGER_DIR / "reports" / ("cleanup_audit_" + __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
        self._background("Полный аудит Import", lambda: audit_all_import_sources(
            samples, STAGING_ROOT, report_path))

    def cleanup(self) -> None:
        try:
            samples = self._samples()
        except Exception as exc:
            messagebox.showerror("Папка Samples", str(exc))
            return
        audit_path = filedialog.askopenfilename(
            title="Выберите полный cleanup_audit_*.json",
            initialdir=str(MANAGER_DIR / "reports"),
            filetypes=[("Cleanup audit", "cleanup_audit_*.json"), ("JSON", "*.json")],
        )
        if not audit_path:
            return
        try:
            audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
            summary = audit["summary"]
            if summary.get("blocked_sources") or summary.get("errors") or summary.get("eligible_for_cleanup") != summary.get("source_files_scanned"):
                messagebox.showwarning(
                    "Очистка заблокирована",
                    "Не все исходники имеют полностью проверенные производные копии. "
                    "Сначала устраните блокировки в отчёте. Ни один файл не удалён."
                )
                return
        except Exception as exc:
            messagebox.showerror("Отчёт очистки", str(exc))
            return
        if not messagebox.askyesno(
            "Удаление оригиналов — подтверждение 1/2",
            f"Аудит охватил все {summary['source_files_scanned']} исходных файлов. "
            "Все зависимости имеют проверенные копии. Удалить оригиналы из Import?"
        ):
            return
        if not messagebox.askyesno(
            "Удаление оригиналов — подтверждение 2/2",
            "Подтверждаете окончательное удаление всех исходников? "
            "Перед удалением аудит и SHA-256 будут проверены повторно."
        ):
            return
        self._background("Очистка исходников", lambda: cleanup_sources_from_audit(
            samples, STAGING_ROOT, Path(audit_path), approve=True,
            confirm_all_dependents_accounted_for=True,
            journal_path=samples / "LibraryManagerReports" / "cleanup.jsonl"))

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
