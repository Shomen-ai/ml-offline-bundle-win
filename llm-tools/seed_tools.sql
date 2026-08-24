-- Примеры строк реестра. Править под свои api.php и выполнять по одной:
-- начинать стоит с одной безобидной ручки на чтение, а не с десяти сразу.
--
-- when_to_use — это НЕ комментарий для человека. Именно этот текст модель
-- читает, решая, какую ручку взять. Писать его надо так, как объяснял бы
-- новому сотруднику: что ручка возвращает и при каких вопросах её брать.
-- Скупое описание — главная причина, по которой модель выбирает не то.
--
-- params — JSON, из которого строится и схема для модели, и валидатор:
--   type: str | int | bool | enum
--   in:   query | path | body
--   enum сильно снижает долю промахов: модель видит допустимые значения
--         прямо в схеме и реже придумывает своё.

-- Ручка без параметров — с такой удобнее всего проверять, что всё завелось.
INSERT INTO dpis_tools (id, name, method, url, when_to_use, params, is_mutating)
VALUES (
    dpis_tools_seq.NEXTVAL,
    'list_projects',
    'GET',
    '/api.php?action=projects',
    'Список проектов с кодами и названиями. Брать, когда спрашивают, какие ' ||
    'вообще есть проекты, или когда нужен код проекта для другого запроса.',
    '{}',
    0
);

-- Параметры: обязательный enum и необязательное число с границами.
INSERT INTO dpis_tools (id, name, method, url, when_to_use, params, is_mutating)
VALUES (
    dpis_tools_seq.NEXTVAL,
    'get_tickets',
    'GET',
    '/api.php?action=tickets',
    'Заявки по проекту в краткой форме: номер, тема, статус, дата. Брать, ' ||
    'когда спрашивают про заявки — сколько открыто, что висит, какие ' ||
    'поступили за период. Код проекта даёт list_projects.',
    '{"project": {"type": "str", "in": "query", "required": true,
                  "desc": "Код проекта, например DPIS"},
      "status":  {"type": "enum", "values": ["open", "closed", "all"],
                  "in": "query", "desc": "Статус заявок, по умолчанию open"},
      "limit":   {"type": "int", "in": "query", "min": 1, "max": 200,
                  "desc": "Сколько записей вернуть, по умолчанию 20"}}',
    0
);

-- Path-параметр подставляется в шаблон вместо {ticket_id}.
INSERT INTO dpis_tools (id, name, method, url, when_to_use, params, is_mutating)
VALUES (
    dpis_tools_seq.NEXTVAL,
    'get_ticket',
    'GET',
    '/api.php?action=ticket&id={ticket_id}',
    'Полная карточка одной заявки: описание, переписка, вложения, история ' ||
    'статусов. Брать, когда спрашивают подробности о конкретной заявке. ' ||
    'Номер заявки даёт get_tickets.',
    '{"ticket_id": {"type": "int", "in": "path", "required": true,
                    "desc": "Номер заявки"}}',
    0
);

-- ИЗМЕНЯЮЩАЯ РУЧКА. is_mutating = 1 означает, что модель не исполнит вызов
-- сама: он попадёт в dpis_tool_calls со статусом pending и будет ждать
-- подтверждения пользователя. Пока подтверждение не дописано (см. заглушку
-- в tools_loop.py), такой вызов отклоняется — то есть строку ниже можно
-- завести заранее, ничего не сломав.
-- INSERT INTO dpis_tools (id, name, method, url, when_to_use, params, is_mutating)
-- VALUES (
--     dpis_tools_seq.NEXTVAL,
--     'create_ticket',
--     'POST',
--     '/api.php?action=ticket_create',
--     'Создать заявку по проекту. Брать ТОЛЬКО когда пользователь прямо ' ||
--     'просит завести заявку и сформулировал тему.',
--     '{"project": {"type": "str", "in": "body", "required": true,
--                   "desc": "Код проекта"},
--       "subject": {"type": "str", "in": "body", "required": true,
--                   "desc": "Тема заявки"}}',
--     1
-- )

COMMIT;
