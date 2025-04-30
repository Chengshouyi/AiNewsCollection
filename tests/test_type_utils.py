"""測試 src.utils.type_utils 中的 AwareDateTime 自訂類型。"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Optional#, Dialect # Dialect 不應從 typing 匯入
import pytz # 確保安裝了 pytz: pip install pytz
import logging

from sqlalchemy.engine import Dialect # Dialect 從這裡匯入

# 本地應用程式導入
from src.utils.type_utils import AwareDateTime


# 設定統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger


# 使用 fixture 提供 AwareDateTime 實例和 dialect
@pytest.fixture
def type_decorator_dialect() -> tuple[AwareDateTime, Optional[Dialect]]:
    """提供 AwareDateTime 實例和模擬的 dialect (None)。"""
    type_decorator = AwareDateTime()
    # AwareDateTime 中未使用 dialect，因此傳遞 None
    dialect: Optional[Dialect] = None
    return type_decorator, dialect


def test_process_bind_param_none(type_decorator_dialect):
    """測試 process_bind_param 處理 None 值。"""
    type_decorator, dialect = type_decorator_dialect
    assert type_decorator.process_bind_param(None, dialect) is None # type: ignore[arg-type]

def test_process_bind_param_naive_datetime(type_decorator_dialect):
    """測試 process_bind_param 處理 naive datetime。"""
    type_decorator, dialect = type_decorator_dialect
    naive_dt = datetime(2023, 10, 27, 10, 30, 0)
    # 預期轉換為 UTC 並格式化
    expected_iso = "2023-10-27T10:30:00+00:00"
    assert type_decorator.process_bind_param(naive_dt, dialect) == expected_iso # type: ignore[arg-type]

def test_process_bind_param_aware_non_utc_datetime(type_decorator_dialect):
    """測試 process_bind_param 處理非 UTC 的 aware datetime。"""
    type_decorator, dialect = type_decorator_dialect
    tz_cest = pytz.timezone('Europe/Berlin') # UTC+2
    aware_dt = tz_cest.localize(datetime(2023, 10, 27, 12, 30, 0)) # 12:30 CEST
    # 預期轉換為 UTC (10:30 UTC) 並格式化
    expected_iso = "2023-10-27T10:30:00+00:00"
    assert type_decorator.process_bind_param(aware_dt, dialect) == expected_iso # type: ignore[arg-type]

    tz_est = pytz.timezone('US/Eastern') # UTC-4 (此日期為 EDT)
    aware_dt_est = tz_est.localize(datetime(2023, 10, 27, 6, 30, 0)) # 06:30 EDT
    expected_iso_est = "2023-10-27T10:30:00+00:00"
    assert type_decorator.process_bind_param(aware_dt_est, dialect) == expected_iso_est # type: ignore[arg-type]


def test_process_bind_param_aware_utc_datetime(type_decorator_dialect):
    """測試 process_bind_param 處理 UTC 的 aware datetime。"""
    type_decorator, dialect = type_decorator_dialect
    aware_utc_dt = datetime(2023, 10, 27, 10, 30, 0, tzinfo=timezone.utc)
    expected_iso = "2023-10-27T10:30:00+00:00"
    assert type_decorator.process_bind_param(aware_utc_dt, dialect) == expected_iso # type: ignore[arg-type]

    aware_utc_dt_offset = datetime(2023, 10, 27, 10, 30, 0, tzinfo=timezone(timedelta(hours=0)))
    assert type_decorator.process_bind_param(aware_utc_dt_offset, dialect) == expected_iso # type: ignore[arg-type]


def test_process_bind_param_invalid_type(type_decorator_dialect):
    """測試 process_bind_param 處理非 datetime 類型。"""
    type_decorator, dialect = type_decorator_dialect
    with pytest.raises(TypeError):
        type_decorator.process_bind_param("not a datetime", dialect) # type: ignore[arg-type]
    with pytest.raises(TypeError):
         type_decorator.process_bind_param(12345, dialect) # type: ignore[arg-type]

def test_process_result_value_none(type_decorator_dialect):
    """測試 process_result_value 處理 None 值。"""
    type_decorator, dialect = type_decorator_dialect
    assert type_decorator.process_result_value(None, dialect) is None # type: ignore[arg-type]

def test_process_result_value_valid_iso_utc(type_decorator_dialect):
    """測試 process_result_value 處理有效的 UTC ISO 字串。"""
    type_decorator, dialect = type_decorator_dialect
    iso_string = "2023-10-27T10:30:00+00:00"
    expected_dt = datetime(2023, 10, 27, 10, 30, 0, tzinfo=timezone.utc)
    result_dt = type_decorator.process_result_value(iso_string, dialect) # type: ignore[arg-type]
    assert result_dt == expected_dt
    assert result_dt is not None # 幫助 type checker 推斷類型
    assert result_dt.tzinfo == timezone.utc


def test_process_result_value_valid_iso_non_utc(type_decorator_dialect):
    """測試 process_result_value 處理有效的非 UTC ISO 字串。"""
    type_decorator, dialect = type_decorator_dialect
    iso_string_cest = "2023-10-27T12:30:00+02:00" # 10:30 UTC
    iso_string_est = "2023-10-27T06:30:00-04:00" # 10:30 UTC
    expected_dt = datetime(2023, 10, 27, 10, 30, 0, tzinfo=timezone.utc)

    result_dt_cest = type_decorator.process_result_value(iso_string_cest, dialect) # type: ignore[arg-type]
    assert result_dt_cest == expected_dt
    assert result_dt_cest is not None
    assert result_dt_cest.tzinfo == timezone.utc

    result_dt_est = type_decorator.process_result_value(iso_string_est, dialect) # type: ignore[arg-type]
    assert result_dt_est == expected_dt
    assert result_dt_est is not None
    assert result_dt_est.tzinfo == timezone.utc


def test_process_result_value_valid_iso_no_offset(type_decorator_dialect):
    """測試 process_result_value 處理沒有時區偏移的 ISO 字串 (視為 naive -> UTC)。"""
    type_decorator, dialect = type_decorator_dialect
    iso_string = "2023-10-27T10:30:00"
    # fromisoformat 會產生 naive，enforce_utc 會將其視為 UTC
    expected_dt = datetime(2023, 10, 27, 10, 30, 0, tzinfo=timezone.utc)
    result_dt = type_decorator.process_result_value(iso_string, dialect) # type: ignore[arg-type]
    assert result_dt == expected_dt
    assert result_dt is not None
    assert result_dt.tzinfo == timezone.utc


def test_process_result_value_invalid_iso(type_decorator_dialect):
    """測試 process_result_value 處理無效的 ISO 字串。"""
    type_decorator, dialect = type_decorator_dialect
    # 根據 AwareDateTime 的實作，它應記錄錯誤並返回 None
    assert type_decorator.process_result_value("invalid-datetime-string", dialect) is None # type: ignore[arg-type]

def test_compare_values_equal(type_decorator_dialect):
    """測試 compare_values 比較相等的時間點。"""
    type_decorator, _ = type_decorator_dialect # dialect 在 compare_values 中不需要
    naive_dt = datetime(2023, 1, 1, 12, 0, 0)
    aware_utc_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    tz_cest = pytz.timezone('Europe/Berlin') # 此日期為 UTC+1
    aware_cest_dt = tz_cest.localize(datetime(2023, 1, 1, 13, 0, 0)) # 12:00 UTC

    tz_est = pytz.timezone('US/Eastern') # 此日期為 UTC-5
    aware_est_dt = tz_est.localize(datetime(2023, 1, 1, 7, 0, 0)) # 12:00 UTC

    # Naive 被視為 UTC
    assert type_decorator.compare_values(naive_dt, aware_utc_dt)
    assert type_decorator.compare_values(aware_utc_dt, naive_dt)

    # 不同時區但相同時間點
    assert type_decorator.compare_values(aware_utc_dt, aware_cest_dt)
    assert type_decorator.compare_values(aware_cest_dt, aware_utc_dt)
    assert type_decorator.compare_values(aware_utc_dt, aware_est_dt)
    assert type_decorator.compare_values(aware_est_dt, aware_utc_dt)
    assert type_decorator.compare_values(aware_cest_dt, aware_est_dt)
    assert type_decorator.compare_values(aware_est_dt, aware_cest_dt)

    # 兩個相同的 aware UTC
    aware_utc_dt_copy = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert type_decorator.compare_values(aware_utc_dt, aware_utc_dt_copy)


def test_compare_values_not_equal(type_decorator_dialect):
    """測試 compare_values 比較不相等的時間點。"""
    type_decorator, _ = type_decorator_dialect
    aware_utc_dt1 = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    aware_utc_dt2 = datetime(2023, 1, 1, 12, 0, 1, tzinfo=timezone.utc) # 差一秒

    tz_cest = pytz.timezone('Europe/Berlin')
    aware_cest_dt = tz_cest.localize(datetime(2023, 1, 1, 13, 0, 1)) # 12:00:01 UTC

    assert not type_decorator.compare_values(aware_utc_dt1, aware_utc_dt2)
    assert not type_decorator.compare_values(aware_utc_dt1, aware_cest_dt)


def test_compare_values_with_non_datetime(type_decorator_dialect):
    """測試 compare_values 比較 datetime 與非 datetime。"""
    type_decorator, _ = type_decorator_dialect
    aware_utc_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert not type_decorator.compare_values(aware_utc_dt, None)
    assert not type_decorator.compare_values(None, aware_utc_dt)
    assert not type_decorator.compare_values(aware_utc_dt, "string")
    assert not type_decorator.compare_values("string", aware_utc_dt)
    assert type_decorator.compare_values(None, None) # None == None
