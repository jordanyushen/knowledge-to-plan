"""Resolve the requested zone without mistaking a missing database for bad input."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimezoneDataError(ValueError):
    """The environment cannot supply even a baseline IANA timezone."""


class InvalidTimezoneError(ValueError):
    """The requested key is malformed or absent from an available database."""


def resolve_timezone(key):
    """Return the user's zone, or an actionable error; never substitute a zone.

    ZoneInfoNotFoundError alone cannot distinguish an unknown key from an
    environment with no database. Probe UTC without using the cache only after
    lookup fails, so ordinary generation keeps the standard ZoneInfo behaviour.
    A partial/outdated database can still miss a valid key; the message includes
    updating tzdata instead of asserting that the key is globally invalid.
    """
    if not isinstance(key, str) or not key.strip():
        raise InvalidTimezoneError('时区必须为非空 IANA 时区名称，例如 Asia/Hong_Kong')
    try:
        return ZoneInfo(key)
    except ValueError as error:
        raise InvalidTimezoneError(
            f'时区 {key!r} 不是规范的 IANA 时区名称；请使用 Asia/Hong_Kong 等相对名称'
        ) from error
    except ZoneInfoNotFoundError as error:
        try:
            ZoneInfo.no_cache('UTC')
        except ZoneInfoNotFoundError:
            raise TimezoneDataError(
                f'当前环境缺少可用的 IANA 时区数据库，无法校验时区 {key!r}。'
                '请在运行本脚本的 Python 环境执行 python -m pip install tzdata，'
                '然后重试；不会自动替换课程时区。'
            ) from error
        raise InvalidTimezoneError(
            f'时区 {key!r} 不在当前可用的 IANA 时区数据库中；'
            '请核对名称（例如 Asia/Hong_Kong）。若名称确实有效，'
            '可执行 python -m pip install --upgrade tzdata 更新数据库后重试。'
        ) from error
