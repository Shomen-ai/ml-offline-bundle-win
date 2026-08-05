-- Схема под Oracle 11g: без IDENTITY-колонок (это 12c+), id через sequence.
-- Применяется скриптом apply_schema.py (или вручную в sqlplus).
--
-- Все объекты схемы несут приставку dpis_ — так они не конфликтуют с чужими
-- таблицами в общей схеме. Приставка зашита в SQL-запросы backend'а; если
-- меняете её здесь, правьте и запросы в app/auth.py, app/chat.py.

-- password_hash/salt заполняются только в локальном режиме авторизации.
-- При входе через Active Directory пароль в базу не попадает и они остаются NULL.
CREATE TABLE dpis_users (
    id            NUMBER        PRIMARY KEY,
    username      VARCHAR2(64)  NOT NULL UNIQUE,
    password_hash VARCHAR2(256),
    salt          VARCHAR2(64),
    created_at    DATE          DEFAULT SYSDATE NOT NULL
);

CREATE SEQUENCE dpis_users_seq;

CREATE TABLE dpis_sessions (
    token      VARCHAR2(128) PRIMARY KEY,
    user_id    NUMBER        NOT NULL REFERENCES dpis_users (id),
    expires_at DATE          NOT NULL,
    created_at DATE          DEFAULT SYSDATE NOT NULL
);

CREATE INDEX dpis_sessions_user_idx ON dpis_sessions (user_id);

-- summary — сжатая сводка начала диалога, summary_upto — id последнего
-- сообщения, которое она покрывает. Заполняются, когда история перестаёт
-- влезать в контекст модели.
CREATE TABLE dpis_dialogs (
    id           NUMBER        PRIMARY KEY,
    user_id      NUMBER        NOT NULL REFERENCES dpis_users (id),
    title        VARCHAR2(200) DEFAULT 'Новый диалог' NOT NULL,
    model_name   VARCHAR2(200),
    summary      CLOB,
    summary_upto NUMBER,
    created_at   DATE          DEFAULT SYSDATE NOT NULL
);

CREATE SEQUENCE dpis_dialogs_seq;

CREATE INDEX dpis_dialogs_user_idx ON dpis_dialogs (user_id);

CREATE TABLE dpis_messages (
    id         NUMBER       PRIMARY KEY,
    dialog_id  NUMBER       NOT NULL REFERENCES dpis_dialogs (id),
    role       VARCHAR2(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content    CLOB,
    created_at TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE SEQUENCE dpis_messages_seq;

CREATE INDEX dpis_messages_dialog_idx ON dpis_messages (dialog_id);

-- Настройки LLM, которые правит админ-панель. Ключ-значение: набор ключей
-- меняется вместе с кодом, а миграций на каждый новый параметр не хочется.
-- Значение CLOB'ом: системный промпт легко перерастает 4000 байт.
-- Имена колонок skey/sval — key и value в Oracle зарезервированы.
CREATE TABLE dpis_settings (
    skey VARCHAR2(64) PRIMARY KEY,
    sval CLOB
);
