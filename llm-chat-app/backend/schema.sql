-- Схема под Oracle 11g: без IDENTITY-колонок (это 12c+), id через sequence.
-- Применяется скриптом apply_schema.py (или вручную в sqlplus).

CREATE TABLE users (
    id            NUMBER        PRIMARY KEY,
    username      VARCHAR2(64)  NOT NULL UNIQUE,
    password_hash VARCHAR2(256) NOT NULL,
    salt          VARCHAR2(64)  NOT NULL,
    created_at    DATE          DEFAULT SYSDATE NOT NULL
);

CREATE SEQUENCE users_seq;

CREATE TABLE sessions (
    token      VARCHAR2(128) PRIMARY KEY,
    user_id    NUMBER        NOT NULL REFERENCES users (id),
    expires_at DATE          NOT NULL,
    created_at DATE          DEFAULT SYSDATE NOT NULL
);

CREATE INDEX sessions_user_idx ON sessions (user_id);

CREATE TABLE dialogs (
    id         NUMBER        PRIMARY KEY,
    user_id    NUMBER        NOT NULL REFERENCES users (id),
    title      VARCHAR2(200) DEFAULT 'Новый диалог' NOT NULL,
    model_name VARCHAR2(200),
    created_at DATE          DEFAULT SYSDATE NOT NULL
);

CREATE SEQUENCE dialogs_seq;

CREATE INDEX dialogs_user_idx ON dialogs (user_id);

CREATE TABLE messages (
    id         NUMBER       PRIMARY KEY,
    dialog_id  NUMBER       NOT NULL REFERENCES dialogs (id),
    role       VARCHAR2(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content    CLOB,
    created_at TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE SEQUENCE messages_seq;

CREATE INDEX messages_dialog_idx ON messages (dialog_id);
