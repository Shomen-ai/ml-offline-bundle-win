"""Режим размышления: блоки <think> в потоке и переключатель /no_think.

Qwen3 умеет думать вслух и оборачивает размышления в <think>…</think>.
Нам они нужны только на экране: в базу не пишутся и в контекст следующего
запроса не подмешиваются — иначе жгут токены и путают модель.

Главная сложность — поток. Дельты приходят кусками произвольной длины,
и тег легко разрывается пополам: «<th» в одной, «ink>» в следующей.
Поэтому это автомат с буфером, а не поиск подстроки: хвост, который
ещё может оказаться началом тега, придерживается до следующей дельты.
"""
OPEN = "<think>"
CLOSE = "</think>"

# что дописываем в конец сообщения, чтобы Qwen3 не размышляла
NO_THINK = "/no_think"


def supports(model: str | None, settings: dict) -> bool:
    """Понимает ли модель переключатель размышлений.

    Список задаётся в настройках, а не зашит в код: у Qwen3 это
    документированное поведение, у более новых моделей — не проверено.
    """
    if not model:
        return False
    allowed = [m.strip() for m in str(settings.get("thinking_models", "")).split(",")]
    return model in [m for m in allowed if m]


def _tail_prefix_len(buf: str, tag: str) -> int:
    """Длина хвоста buf, который ещё может оказаться началом tag."""
    for n in range(min(len(buf), len(tag) - 1), 0, -1):
        if buf.endswith(tag[:n]):
            return n
    return 0


class Splitter:
    """Делит поток дельт на размышления и собственно ответ.

    feed() отдаёт список пар ('think' | 'text', кусок). В конце потока
    обязателен flush(): в буфере может остаться придержанный хвост.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._inside = False
        self._seen_text = False

    def feed(self, chunk: str) -> list[tuple[str, str]]:
        self._buf += chunk
        return self._drain(final=False)

    def flush(self) -> list[tuple[str, str]]:
        return self._drain(final=True)

    def _drain(self, final: bool) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        while True:
            tag = CLOSE if self._inside else OPEN
            idx = self._buf.find(tag)
            if idx >= 0:
                head = self._buf[:idx]
                self._buf = self._buf[idx + len(tag) :]
                if head:
                    out.append(self._emit(head))
                self._inside = not self._inside
                continue
            # тега нет: придерживаем хвост, который может им оказаться
            keep = 0 if final else _tail_prefix_len(self._buf, tag)
            ready = self._buf[: len(self._buf) - keep]
            self._buf = self._buf[len(self._buf) - keep :]
            if ready:
                out.append(self._emit(ready))
            break
        return [item for item in out if item[1]]

    def _emit(self, text: str) -> tuple[str, str]:
        if self._inside:
            return ("think", text)
        if not self._seen_text:
            # после </think> модель обычно начинает с переводов строк
            text = text.lstrip()
            if text:
                self._seen_text = True
        return ("text", text)
