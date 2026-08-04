"""Аутентификация в Active Directory через LDAP.

Включается, когда в .env задан LDAP_URL. Пароли в этом режиме в БД не хранятся
вообще: проверка — попытка bind'а в каталог под введёнными логином и паролем,
ровно как Auth::guard('ldap')->attempt() в Laravel.

Зависимость: ldap3 (чистый Python, без C-расширений). В офлайн-бандл она
изначально не входила — колесо переносится отдельно, см. README.
"""
import logging

from . import config

log = logging.getLogger(__name__)


def enabled() -> bool:
    """LDAP настроен? Если нет — работает прежний вход по паролю из БД."""
    return bool(config.LDAP_URL)


def _bind_name(username: str) -> str:
    """AD принимает user@domain (UPN). Без домена — отдаём логин как есть."""
    if config.LDAP_DOMAIN and "@" not in username and "\\" not in username:
        return f"{username}@{config.LDAP_DOMAIN}"
    return username


def authenticate(username: str, password: str) -> dict | None:
    """Проверяет пару логин/пароль. None — каталог отказал.

    При успехе возвращает атрибуты пользователя: {'username', 'display_name',
    'email'}. Пустой пароль отсекаем сами: AD на пустой пароль отвечает
    "unauthenticated bind" — успешным bind'ом без всякой проверки.
    """
    if not password:
        return None

    try:
        from ldap3 import ALL, Connection, Server
        from ldap3.core.exceptions import LDAPException
        from ldap3.utils.conv import escape_filter_chars
    except ImportError as e:  # pragma: no cover — зависит от машины
        raise RuntimeError(
            "LDAP_URL задан, но пакет ldap3 не установлен. "
            "Перенесите колесо ldap3 (+ pyasn1) и поставьте: "
            "pip install --no-index --find-links=D:\\transfer\\wheels ldap3"
        ) from e

    server = Server(config.LDAP_URL, get_info=ALL, connect_timeout=config.LDAP_TIMEOUT)
    conn = None
    try:
        conn = Connection(
            server,
            user=_bind_name(username),
            password=password,
            auto_bind=False,
            receive_timeout=config.LDAP_TIMEOUT,
        )
        if not conn.bind():
            log.info("LDAP: отказ для %s (%s)", username, conn.result.get("description"))
            return None

        # Пароль уже подтверждён bind'ом. Атрибуты — необязательная добавка,
        # поэтому её ошибки не должны превращаться в отказ во входе.
        person = {"username": username, "display_name": "", "email": ""}
        if config.LDAP_BASE_DN:
            try:
                safe = escape_filter_chars(username)
                conn.search(
                    search_base=config.LDAP_BASE_DN,
                    search_filter=f"({config.LDAP_USER_ATTR}={safe})",
                    attributes=["displayName", "mail"],
                    size_limit=1,
                )
                if conn.entries:
                    entry = conn.entries[0]
                    person["display_name"] = str(entry.displayName or "")
                    person["email"] = str(entry.mail or "")
            except LDAPException:
                log.warning("LDAP: не удалось прочитать атрибуты %s", username, exc_info=True)
        return person
    except LDAPException:
        # недоступный контроллер домена, таймаут, кривой BASE_DN — не пускаем,
        # но и не выдаём наружу подробности каталога
        log.exception("LDAP: ошибка обращения к каталогу")
        return None
    finally:
        if conn is not None and conn.bound:
            conn.unbind()
