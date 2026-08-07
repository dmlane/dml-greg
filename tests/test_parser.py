import pytest
import time
import argparse
from greg.parser import from_date, url

def test_from_date_now():
    # 'now' should return current local time as a list
    result = from_date("now")
    now = list(time.localtime())
    # We check if it's close enough (ignoring seconds might be risky, but usually it matches)
    assert result[:5] == now[:5]

def test_from_date_specific():
    # Valid date format
    result = from_date("2023-12-25")
    expected = list(time.strptime("2023-12-25", "%Y-%m-%d"))
    assert result == expected

def test_from_date_invalid():
    # Invalid date format
    with pytest.raises(argparse.ArgumentTypeError) as excinfo:
        from_date("25-12-2023")
    assert "the date should be in the form YYYY-MM-DD" in str(excinfo.value)

    with pytest.raises(argparse.ArgumentTypeError):
        from_date("not-a-date")

def test_url_valid():
    assert url("http://example.com") == "http://example.com"
    assert url("https://example.com/feed.xml") == "https://example.com/feed.xml"

def test_url_invalid():
    # Missing netloc
    with pytest.raises(argparse.ArgumentTypeError) as excinfo:
        url("example.com")
    assert "does not appear to be an url" in str(excinfo.value)

    with pytest.raises(argparse.ArgumentTypeError):
        url("ftp://")
