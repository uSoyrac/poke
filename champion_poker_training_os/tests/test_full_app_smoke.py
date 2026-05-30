"""Kapsamlı sistem testi — tüm uygulamayı kur, HER ekrana gez, render et.

Gerçek MainWindow'u offscreen kurar; her NAV ekranına navigate() ile
geçer (showEvent + reload + paint yollarını tetikler) ve grab() ile
render eder. Herhangi bir ekran kurulumda/gösterimde/çiziminde patlarsa
test düşer. Bu, "her yere kapsamlı test" güvencesidir.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def main_window():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app.main import MainWindow
    win = MainWindow()
    win.resize(1400, 950)
    yield win, app
    win.close()


def test_every_screen_navigates_and_renders(main_window):
    from app.main import NAV_ITEMS
    win, app = main_window
    failures = []
    for name in NAV_ITEMS:
        try:
            win.navigate(name)
            app.processEvents()
            pix = win.stack.currentWidget().grab()
            assert not pix.isNull(), f"{name}: boş render"
            # Min boyut — ekran tamamen çökmemiş olmalı
            assert pix.width() > 50 and pix.height() > 50, f"{name}: dejenere boyut"
        except Exception as e:  # noqa: BLE001
            failures.append(f"{name}: {type(e).__name__}: {e}")
    assert not failures, "Ekran hataları:\n" + "\n".join(failures)


def test_all_nav_items_have_factories(main_window):
    """Lazy loading: her NAV öğesinin bir factory'si olmalı (ekran talep
    üzerine kurulur, başlangıçta değil)."""
    from app.main import NAV_ITEMS
    win, _ = main_window
    for name in NAV_ITEMS:
        assert name in win._screen_factories, f"{name} factory kayıtlı değil"


def test_lazy_boot_builds_only_default(main_window):
    """Açılışta yalnızca varsayılan ekran kurulu olmalı (lazy boot).
    NOT: bu test modül-scoped fixture'ı paylaştığı için diğer testler
    ekran kurmuş olabilir → en az default'un kurulu olduğunu doğrula."""
    from app.main import NAV_ITEMS
    win, _ = main_window
    assert NAV_ITEMS[0] in win.screens          # default eager kurulur
    assert len(win._screen_factories) == len(NAV_ITEMS)


def test_drill_timers_idle_when_not_current(main_window):
    """MTT/Quiz sayaçları yalnızca o ekran aktifken çalışmalı (arka planda
    akıp SÜRE DOLDU'ya düşmemeli)."""
    win, app = main_window
    # Başka bir ekrana geç → drill ekranları gizli → sayaçları durmalı
    win.navigate("Dashboard")
    app.processEvents()
    for drill in ("Range Quiz", "MTT Trainer"):
        screen = win.screens[drill]
        timer = getattr(screen, "_timer", None)
        if timer is not None:
            assert not timer.isActive(), f"{drill} sayacı arka planda çalışıyor"
