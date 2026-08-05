"""Сборка контекста для модели: бюджет токенов, обрезка, сжатие истории.

Раньше в модель уходили последние N сообщений штуками. Штуки не имеют
отношения к токенам, поэтому длинный диалог не «забывал старое», а падал
с ошибкой переполнения контекста — и падал уже навсегда, потому что
каждая следующая попытка тащила ту же историю.

Теперь история набирается с конца, пока влезает в бюджет, а то, что за
борт, сжимается моделью в сводку и хранится в самом диалоге. Системный
промпт и сводка закреплены: их не выбрасывает никогда.

Функции подсчёта и отбора чистые — их можно проверять без Oracle и GPU.
"""
import math

from anyio import to_thread

from . import dialogs as dialog_service
from . import llm_client
from . import messages as message_service

# накладные расходы шаблона чата на каждое сообщение (маркеры ролей)
PER_MESSAGE_OVERHEAD = 8
# запас на служебные токены самого шаблона
RESERVE = 64
# сколько раз подряд готовы сжимать, прежде чем просто отбросить лишнее
MAX_COMPRESSIONS = 2
# потолок длины самой сводки
SUMMARY_MAX_TOKENS = 512

SUMMARY_PREFIX = "Краткое содержание начала диалога:\n"

_SUMMARY_SYSTEM = (
    "Ты сжимаешь переписку пользователя с ассистентом. Верни краткий пересказ "
    "на русском: факты, решения, договорённости, незакрытые вопросы. "
    "Без вступлений и без оценок — только содержание."
)


def compute_budget(n_ctx: int, max_tokens: int) -> int:
    """Сколько токенов остаётся под историю после места под ответ."""
    return max(256, n_ctx - max_tokens - RESERVE)


def fit(counts: list[int], budget: int) -> int:
    """Индекс первого сообщения, которое влезает, если набирать с конца.

    Вернёт len(counts), если не влезает ни одно, и 0, если влезают все.
    """
    total = 0
    index = len(counts)
    for i in range(len(counts) - 1, -1, -1):
        need = counts[i] + PER_MESSAGE_OVERHEAD
        if total + need > budget:
            break
        total += need
        index = i
    return index


def take_for_compression(counts: list[int], limit: int) -> int:
    """Сколько самых старых сообщений отдать на сжатие за один заход.

    Промпт сжатия сам должен влезать в контекст, поэтому берём префикс
    по бюджету — но не меньше одного сообщения, иначе не сдвинемся.
    """
    total = 0
    taken = 0
    for count in counts:
        if taken and total + count > limit:
            break
        total += count
        taken += 1
    return max(1, taken)


def estimate(texts: list[str]) -> list[int]:
    """Грубая оценка на случай недоступной ручки /tokenize.

    Для кириллицы отношение знаков к токенам гуляет от 2 до 4, берём
    осторожные 2.5 — лучше недобрать историю, чем упереться в лимит.
    """
    return [math.ceil(len(t) / 2.5) + 2 for t in texts]


async def count_tokens(texts: list[str], model: str | None) -> list[int]:
    if not texts:
        return []
    try:
        return await llm_client.tokenize(texts, model)
    except Exception:
        return estimate(texts)


async def fits_alone(text: str, settings: dict) -> bool:
    """Влезает ли одно сообщение в контекст вообще.

    Проверяется до записи в базу: иначе в истории остаётся сообщение,
    на которое модель физически не может ответить.
    """
    budget = compute_budget(settings["n_ctx"], settings["max_tokens"])
    counts = await count_tokens([text], settings["model_name"])
    return counts[0] + PER_MESSAGE_OVERHEAD <= budget


async def _summarize(previous: str, rows: list[dict], settings: dict) -> str:
    lines = []
    for row in rows:
        who = "Пользователь" if row["role"] == "user" else "Ассистент"
        lines.append(f"{who}: {row['content'] or ''}")
    body = "\n".join(lines)
    if previous:
        body = f"Уже известно:\n{previous}\n\nПродолжение переписки:\n{body}"

    text = await llm_client.complete(
        [
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": body},
        ],
        settings["model_name"],
        max_tokens=SUMMARY_MAX_TOKENS,
        temperature=0.2,
    )
    return text.strip()


async def assemble(dialog_id: int, settings: dict):
    """Асинхронный генератор: ('status', текст) по ходу и ('messages', список) в конце.

    Статус нужен, потому что сжатие — это отдельная генерация, и на
    однопоточном LLM-сервере она заметно тормозит ответ. Молчащий экран
    в этот момент выглядит зависанием.
    """
    model = settings["model_name"]
    budget = compute_budget(settings["n_ctx"], settings["max_tokens"])

    for attempt in range(MAX_COMPRESSIONS + 1):
        state = await to_thread.run_sync(dialog_service.get_summary, dialog_id)
        rows = await to_thread.run_sync(
            message_service.list_after, dialog_id, state["summary_upto"]
        )

        head: list[dict] = []
        if settings["system_prompt"]:
            head.append({"role": "system", "content": settings["system_prompt"]})
        if state["summary"]:
            head.append({"role": "system", "content": SUMMARY_PREFIX + state["summary"]})

        texts = [m["content"] for m in head] + [r["content"] or "" for r in rows]
        counts = await count_tokens(texts, model)
        head_counts, body_counts = counts[: len(head)], counts[len(head) :]
        head_tokens = sum(head_counts) + PER_MESSAGE_OVERHEAD * len(head)

        start = fit(body_counts, budget - head_tokens)
        tail = [{"role": r["role"], "content": r["content"] or ""} for r in rows[start:]]

        if start == 0 or not rows or attempt == MAX_COMPRESSIONS:
            # влезло всё; либо сжимать больше нельзя — отдаём что уместилось
            yield "messages", head + tail
            return

        yield "status", "сжимаю историю"
        # промпт сжатия сам должен влезть в контекст, но брать меньше, чем
        # позволяет свободное место, незачем: каждый заход — отдельная
        # генерация, и лишние заходы напрямую бьют по времени ответа
        take = take_for_compression(body_counts[:start], max(256, budget - head_tokens))
        to_compress = rows[:take]
        summary = await _summarize(state["summary"], to_compress, settings)
        await to_thread.run_sync(
            dialog_service.set_summary, dialog_id, summary, int(to_compress[-1]["id"])
        )
