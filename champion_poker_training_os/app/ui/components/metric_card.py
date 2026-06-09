from __future__ import annotations

from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy,
                               QVBoxLayout)


class MetricCard(QFrame):
    """Brutalist KPI stat tile: label, big value, sub-detail."""

    def __init__(self, title: str, value: str, detail: str = "", accent: str = "Mono"):
        super().__init__()
        self.setObjectName("MetricCard")
        # D134 RESPONSIVE: kart küçülebilsin — yoksa metin genişliği onu içeren
        # meta/stat bar'ı geniş bir min'e zorlayıp dar pencerede taşırıyordu.
        # Ignored-genişlik etiketler → dar alanda metin kart İÇİNDE kırpılır,
        # tüm ekran taşmaz. (play_session, dashboard, icm, reports hepsi faydalanır.)
        self.setMinimumWidth(56)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("TLabel")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")

        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName(accent or "Mono")
        self.detail_label.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px;"
        )

        for _w in (self.title_label, self.value_label, self.detail_label):
            _w.setMinimumWidth(0)
            _w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_detail(self, detail: str, accent: str = "") -> None:
        self.detail_label.setText(detail)
        if accent:
            self.detail_label.setObjectName(accent)
            self.detail_label.style().unpolish(self.detail_label)
            self.detail_label.style().polish(self.detail_label)
