-- Реестр инструментов и журнал вызовов. Дополнение к llm-chat-app/backend/schema.sql.
--
-- Применять на базе, где таблицы чата УЖЕ созданы: этот файл ничего не пересоздаёт
-- и не трогает существующие объекты. Кладётся в backend/migrations/ и запускается
-- как остальные миграции.
--
-- Приставка dpis_ — как у всей схемы, чтобы не конфликтовать в общей схеме.

-- Инструмент = URL плюс описание, когда его применять. Никакого Swagger не нужно:
-- строку заводит человек через админ-панель.
--
-- params — JSON с описанием параметров, из него на лету строится pydantic-модель
-- и JSON-схема для модели. Формат (ключ = имя параметра):
--   {"category": {"type": "enum", "values": ["a","b"], "in": "query",
--                 "desc": "...", "required": false}}
-- type: str | int | bool | enum,  in: query | path | body
--
-- CLOB, а не VARCHAR2: описание when_to_use — главный рычаг качества выбора
-- инструмента, его пишут развёрнуто и 4000 байт кончаются быстрее, чем кажется.
CREATE TABLE dpis_tools (
    id          NUMBER        PRIMARY KEY,
    name        VARCHAR2(64)  NOT NULL UNIQUE,
    method      VARCHAR2(8)   DEFAULT 'GET' NOT NULL CHECK (method IN ('GET', 'POST')),
    url         VARCHAR2(500) NOT NULL,
    when_to_use CLOB          NOT NULL,
    params      CLOB,
    -- Изменяющая ручка не исполняется сразу: пользователь подтверждает вызов
    -- кнопкой в чате. Ставить 1 для всего, что создаёт, правит или удаляет.
    is_mutating NUMBER(1)     DEFAULT 0 NOT NULL CHECK (is_mutating IN (0, 1)),
    -- Выключенный инструмент не попадает в промпт вообще: это способ убрать
    -- ручку из виду модели, не удаляя её описание.
    enabled     NUMBER(1)     DEFAULT 1 NOT NULL CHECK (enabled IN (0, 1)),
    created_at  DATE          DEFAULT SYSDATE NOT NULL
);

CREATE SEQUENCE dpis_tools_seq;

-- Журнал вызовов. Нужен по двум причинам: разбирать, почему модель ответила
-- ерундой, и отвечать на вопрос «кто и что дёрнул в рабочей системе».
-- Для изменяющих ручек это не журнал удобства, а журнал ответственности,
-- поэтому пишется ДО исполнения, а не после.
CREATE TABLE dpis_tool_calls (
    id          NUMBER       PRIMARY KEY,
    dialog_id   NUMBER       NOT NULL REFERENCES dpis_dialogs (id),
    user_id     NUMBER       NOT NULL REFERENCES dpis_users (id),
    tool_name   VARCHAR2(64) NOT NULL,
    args        CLOB,
    -- pending  — ждёт подтверждения пользователя (только изменяющие)
    -- ok       — выполнен успешно
    -- rejected — аргументы не прошли валидацию, до сети не дошло
    -- failed   — сеть или ошибка удалённого api.php
    -- declined — пользователь отказался подтверждать
    status      VARCHAR2(16) NOT NULL
                CHECK (status IN ('pending', 'ok', 'rejected', 'failed', 'declined')),
    error       VARCHAR2(500),
    result_len  NUMBER,
    created_at  TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE SEQUENCE dpis_tool_calls_seq;

CREATE INDEX dpis_tool_calls_dialog_idx ON dpis_tool_calls (dialog_id);


-- Новые ключи настроек. Таблица dpis_settings уже есть, добавляются только строки,
-- MERGE — чтобы миграцию можно было прогнать повторно, ничего не сломав.
MERGE INTO dpis_settings t USING (SELECT 'tools_enabled' AS skey FROM dual) s
    ON (t.skey = s.skey)
    WHEN NOT MATCHED THEN INSERT (skey, sval) VALUES ('tools_enabled', '0');

MERGE INTO dpis_settings t USING (SELECT 'tools_max_steps' AS skey FROM dual) s
    ON (t.skey = s.skey)
    WHEN NOT MATCHED THEN INSERT (skey, sval) VALUES ('tools_max_steps', '5');

MERGE INTO dpis_settings t USING (SELECT 'tools_result_limit' AS skey FROM dual) s
    ON (t.skey = s.skey)
    WHEN NOT MATCHED THEN INSERT (skey, sval) VALUES ('tools_result_limit', '2000');

COMMIT;
