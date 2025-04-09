from datetime import datetime, timezone, timedelta
from src.utils.datetime_utils import enforce_utc_datetime_transform


def test_enforce_utc_naive_datetime():
    """
    測試輸入一個 naive (無時區資訊) 的 datetime 物件。
    根據目前的程式碼邏輯 (Option 1)，它應該被視為 UTC 並加上 UTC 時區。
    """
    naive_dt = datetime(2024, 3, 29, 10, 30, 0)
    expected_dt = datetime(2024, 3, 29, 10, 30, 0, tzinfo=timezone.utc)
    
    result_dt = enforce_utc_datetime_transform(naive_dt)
    
    assert result_dt == expected_dt
    assert result_dt.tzinfo == timezone.utc
    print(f"\nNaive Input: {naive_dt} -> Output: {result_dt} (Expected: {expected_dt})")

def test_enforce_utc_already_utc():
    """
    測試輸入一個已經是 UTC 時區的 aware datetime 物件。
    應該直接返回原物件。
    """
    utc_dt = datetime(2024, 3, 29, 10, 30, 0, tzinfo=timezone.utc)
    expected_dt = utc_dt # 預期結果與輸入相同
    
    result_dt = enforce_utc_datetime_transform(utc_dt)
    
    assert result_dt == expected_dt
    assert result_dt.tzinfo == timezone.utc
    # 驗證返回的是同一個物件 (如果這是期望行為)
    # assert result_dt is utc_dt # 在這個案例中，函數會直接 return value，所以是同一個物件
    print(f"\nAlready UTC Input: {utc_dt} -> Output: {result_dt} (Expected: {expected_dt})")


def test_enforce_utc_other_timezone_positive_offset():
    """
    測試輸入一個非 UTC 時區 (正時差) 的 aware datetime 物件。
    應該轉換為正確的 UTC 時間。
    """
    # 例如：台北時間 (UTC+8)
    tz_taipei = timezone(timedelta(hours=8))
    taipei_dt = datetime(2024, 3, 29, 18, 30, 0, tzinfo=tz_taipei) # 台北時間下午 6:30
    # 預期的 UTC 時間應該是 18:30 - 8 小時 = 10:30
    expected_dt = datetime(2024, 3, 29, 10, 30, 0, tzinfo=timezone.utc)
    
    result_dt = enforce_utc_datetime_transform(taipei_dt)
    
    assert result_dt == expected_dt
    assert result_dt.tzinfo == timezone.utc
    print(f"\n+8 TZ Input: {taipei_dt} -> Output: {result_dt} (Expected: {expected_dt})")

def test_enforce_utc_other_timezone_negative_offset():
    """
    測試輸入一個非 UTC 時區 (負時差) 的 aware datetime 物件。
    應該轉換為正確的 UTC 時間。
    """
    # 例如：紐約時間 (假設是 UTC-5，不考慮夏令時)
    tz_new_york = timezone(timedelta(hours=-5))
    new_york_dt = datetime(2024, 3, 29, 5, 30, 0, tzinfo=tz_new_york) # 紐約時間早上 5:30
    # 預期的 UTC 時間應該是 5:30 + 5 小時 = 10:30
    expected_dt = datetime(2024, 3, 29, 10, 30, 0, tzinfo=timezone.utc)
    
    result_dt = enforce_utc_datetime_transform(new_york_dt)
    
    assert result_dt == expected_dt
    assert result_dt.tzinfo == timezone.utc
    print(f"\n-5 TZ Input: {new_york_dt} -> Output: {result_dt} (Expected: {expected_dt})")
