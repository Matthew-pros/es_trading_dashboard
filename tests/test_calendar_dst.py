from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from src.calendar import display_prague, provisional_cutoff, session_close

def test_timezone_conversion_across_dst():
    winter=display_prague(datetime(2024,1,15,16,0,tzinfo=ZoneInfo("America/New_York")))
    summer=display_prague(datetime(2024,7,15,16,0,tzinfo=ZoneInfo("America/New_York")))
    assert winter.hour==22 and summer.hour==22

def test_provisional_cutoff_requires_calendar():
    pytest.importorskip("pandas_market_calendars")
    from datetime import date
    cutoff=provisional_cutoff(date(2024,7,3)); close=session_close(date(2024,7,3))
    assert close is not None and cutoff is not None
    assert (close-cutoff).total_seconds()==900
