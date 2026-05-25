from __future__ import annotations

import os
from typing import Callable

from PySide6.QtCore import QThread, Signal

from app.ai.coach_prompts import SYSTEM_PROMPT_TR

try:
    from google import genai
    from google.genai import types as genai_types
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False


def _get_profile() -> str:
    """Oyuncu profilini oku — import hatası veya DB hatası sessizce atlanır."""
    try:
        from app.ai.player_profile import build_profile_text
        return build_profile_text()
    except Exception:
        return ""


class _GeminiThread(QThread):
    response_ready = Signal(str)

    def __init__(self, client, history: list, prompt: str, system: str):
        super().__init__()
        self._client = client
        self._history = list(history)
        self._prompt = prompt
        self._system = system

    def run(self) -> None:
        try:
            contents = list(self._history) + [
                genai_types.Content(role="user", parts=[genai_types.Part(text=self._prompt)])
            ]
            resp = self._client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=self._system,
                    temperature=0.7,
                ),
            )
            self.response_ready.emit(resp.text)
        except Exception as exc:
            self.response_ready.emit(f"⚠️ Gemini hatası: {exc}")


class GeminiCoach:
    """Gemini 2.5 Flash powered poker coach.

    Her istekte:
    1. DB'den oyuncu profili okunur (VPIP/PFR/leak'ler)
    2. Profil sistem promptuna eklenir
    3. Gemini kişiselleştirilmiş analiz üretir
    """

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._available = False
        self._client = None
        self._history: list = []
        self._thread: _GeminiThread | None = None

        if _HAS_GEMINI and key:
            try:
                self._client = genai.Client(api_key=key)
                self._available = True
            except Exception:
                self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def ask_async(self, prompt: str, on_result: Callable[[str], None]) -> None:
        """Ask Gemini in a background QThread. on_result(text) called when done."""
        if not self._available or self._client is None:
            on_result("Gemini bağlantısı yok — offline mod aktif.")
            return
        if self._thread and self._thread.isRunning():
            return  # ignore while a request is in flight

        # Her istekte taze profil — DB değiştikçe otomatik güncellenir
        profile = _get_profile()
        system = SYSTEM_PROMPT_TR
        if profile:
            system = f"{SYSTEM_PROMPT_TR}\n\n{profile}"

        self._thread = _GeminiThread(self._client, self._history, prompt, system)
        self._thread.response_ready.connect(
            lambda text, p=prompt: self._on_response(p, text, on_result)
        )
        self._thread.start()

    def _on_response(self, prompt: str, text: str, on_result: Callable[[str], None]) -> None:
        self._history.append(
            genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])
        )
        self._history.append(
            genai_types.Content(role="model", parts=[genai_types.Part(text=text)])
        )
        if len(self._history) > 40:
            self._history = self._history[-40:]
        on_result(text)

    def reset_chat(self) -> None:
        self._history.clear()
