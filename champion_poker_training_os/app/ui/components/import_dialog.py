"""HandHistoryImportDialog — Poke-styled hand-history import flow.

Two paths, one dialog:

    ┌───────────────────────────────────────────────────────┐
    │ 23 / IMPORT                                           │
    │  Pull in your <em>history</em>.                       │
    │  PokerStars · CoinPoker · auto-detect                 │
    │                                                       │
    │ A1  FROM FILE        Pick file(s)            B Browse │
    │ A2  PASTE TEXT       [ paste box (multi-line) ]       │
    │                                                       │
    │                              [Cancel] [Import]        │
    └───────────────────────────────────────────────────────┘

On accept:
  • Files OR paste text are routed to `parse_hand_history()`.
  • Parsed hands are persisted via `save_imported_hands()`.
  • A summary dict is exposed via `.result` for the caller to act on.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
    QVBoxLayout, QWidget,
)

from app.db.repository import save_imported_hands, imported_hands_count
from app.parsers.hand_history_parser import parse_hand_history
from app.ui.components.poke import (
    PokeBtn, PokeCard, PokePageHeader, PokeTag,
)
from app.ui.theme import poke_tokens as t


class HandHistoryImportDialog(QDialog):
    """Modal dialog. Inspect ``.result`` after ``exec()`` for outcome."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Import hand history")
        self.setModal(True)
        self.setMinimumWidth(720)
        self.setMinimumHeight(560)
        self.result_summary: dict = {
            "saved":  0,
            "files":  0,
            "failed": 0,
            "site":   "—",
        }
        self._picked_paths: list[str] = []

        self.setStyleSheet(
            f"QDialog {{ background: {t.BG}; }}"
            f"QLabel {{ color: {t.INK}; background: transparent; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(t.PAGE_PAD, t.PAGE_PAD, t.PAGE_PAD, 24)
        root.setSpacing(16)

        # ── Page header ────────────────────────────────────────────
        root.addWidget(PokePageHeader(
            num="23 / Import",
            title="Pull in your <em>history</em>.",
            sub=("PokerStars · CoinPoker · GGPoker · auto-detected. "
                 f"Şu an: {imported_hands_count()} hand imported."),
        ))

        # ── A1: file picker card ───────────────────────────────────
        file_card = PokeCard(
            "From file",
            num="A1",
            sub="*.TXT · *.LOG · *.HH",
        )
        file_card.body_layout().setSpacing(10)

        self._files_label = QLabel("No files selected.")
        self._files_label.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px;"
        )
        self._files_label.setWordWrap(True)
        file_card.add_to_body(self._files_label)

        pick_row = QHBoxLayout()
        pick_row.setSpacing(8)
        browse = PokeBtn("Browse files…", variant="default", size="md",
                          kbd="B")
        browse.clicked.connect(self._browse)
        pick_row.addWidget(browse)
        clear = PokeBtn("Clear", variant="ghost", size="md")
        clear.clicked.connect(self._clear_files)
        pick_row.addWidget(clear)
        pick_row.addStretch(1)
        file_card.add_layout_to_body(pick_row)

        root.addWidget(file_card)

        # ── A2: paste card ─────────────────────────────────────────
        paste_card = PokeCard(
            "Paste text",
            num="A2",
            sub="ALT TO FILES",
        )
        paste_card.body_layout().setSpacing(8)

        self._paste_box = QPlainTextEdit()
        self._paste_box.setPlaceholderText(
            "Paste raw hand-history text here…\n\n"
            "Example: 'PokerStars Hand #...' / 'CoinPoker Hand #...'\n"
            "Auto-detects format. Files above take precedence."
        )
        self._paste_box.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background: {t.BG_2}; color: {t.INK};"
            f"  border: 1px solid {t.LINE_2};"
            f"  font-family: 'JetBrains Mono'; font-size: 11px;"
            f"  padding: 10px;"
            f"}}"
            f"QPlainTextEdit:focus {{ border-color: {t.ACCENT}; }}"
        )
        self._paste_box.setMinimumHeight(180)
        paste_card.add_to_body(self._paste_box)
        root.addWidget(paste_card, 1)

        # ── Footer (cancel + import) ───────────────────────────────
        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.status = QLabel("")
        self.status.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px;"
        )
        footer.addWidget(self.status, 1)

        cancel = PokeBtn("Cancel", variant="ghost", size="md")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)

        self._import_btn = PokeBtn(
            "Import", variant="primary", size="md", kbd="↵",
        )
        self._import_btn.clicked.connect(self._do_import)
        footer.addWidget(self._import_btn)
        root.addLayout(footer)

    # ── helpers ────────────────────────────────────────────────────
    def _browse(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import PokerStars / CoinPoker / GG hand history",
            "", "Hand history files (*.txt *.log *.hh);;All files (*)",
        )
        if not paths:
            return
        self._picked_paths = list(paths)
        names = [Path(p).name for p in paths]
        if len(names) <= 4:
            self._files_label.setText(f"Selected: {', '.join(names)}")
        else:
            self._files_label.setText(
                f"Selected: {len(names)} files (e.g. {names[0]}, "
                f"{names[1]}, …)"
            )
        self._files_label.setStyleSheet(
            f"color: {t.INK}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px; font-weight: 600;"
        )

    def _clear_files(self) -> None:
        self._picked_paths = []
        self._files_label.setText("No files selected.")
        self._files_label.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px;"
        )

    def _do_import(self) -> None:
        """Parse + persist whatever the user provided. Closes on success."""
        total_saved = 0
        total_files = 0
        total_failed = 0
        sites: set[str] = set()

        # Files first (more reliable than paste)
        for path in self._picked_paths:
            total_files += 1
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except Exception:
                total_failed += 1
                continue
            parsed = parse_hand_history(text)
            if not parsed:
                total_failed += 1
                continue
            total_saved += save_imported_hands(parsed)
            for h in parsed[:1]:
                sites.add(h.get("source") or h.get("site") or "Unknown")

        # Then any pasted text
        pasted = self._paste_box.toPlainText().strip()
        if pasted:
            parsed = parse_hand_history(pasted)
            if parsed:
                total_saved += save_imported_hands(parsed)
                for h in parsed[:1]:
                    sites.add(h.get("source") or h.get("site") or "Unknown")
            else:
                total_failed += 1

        # Nothing actionable
        if not self._picked_paths and not pasted:
            self.status.setText(
                "Pick file(s) or paste hand-history text first."
            )
            return

        self.result_summary = {
            "saved":  total_saved,
            "files":  total_files,
            "failed": total_failed,
            "site":   ", ".join(sorted(sites)) or "—",
        }
        if total_saved > 0:
            self.accept()
        else:
            self.status.setText(
                f"No hands parsed. {total_failed} source(s) had no "
                "recognisable PokerStars/CoinPoker hand blocks."
            )
