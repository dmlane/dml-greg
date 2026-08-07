import pytest
import os
import json
from greg.aux_functions import sanitize, feedburner_date_handler, parse_for_download, parse_feed_info

def test_sanitize():
    assert sanitize("Hello World") == "Hello_World"
    # Current behavior: NFKD separates accents, then isalnum filters them, 
    # resulting in underscores for the accents.
    assert sanitize("Héllò") == "He_llo_" 
    assert sanitize("file!name@123") == "file_name_123"
    assert sanitize("   ") == "___"
    assert sanitize("") == ""

def test_feedburner_date_handler():
    # Valid date
    date_str = "Sunday, November 25, 2012 - 12:00"
    expected = (2012, 11, 25, 12, 0, 0, 0, 0, 0)
    assert feedburner_date_handler(date_str) == expected

    # Another valid date
    date_str = "Monday, January 1, 2024 - 08:30"
    expected = (2024, 1, 1, 8, 30, 0, 0, 0, 0)
    assert feedburner_date_handler(date_str) == expected

    # Invalid format
    assert feedburner_date_handler("2012-11-25") is None
    assert feedburner_date_handler("Invalid Date") is None

def test_parse_for_download():
    # Normal case with commas
    args = {"number": ["4,", "6-8,", "10"]}
    assert parse_for_download(args) == ["4", "6", "7", "8", "10"]

    # Case without commas (concatenation behavior)
    args = {"number": ["4", "5"]}
    # single_arg becomes " 4 5" -> "45"
    assert parse_for_download(args) == ["45"]

    # Range case
    args = {"number": ["1-3"]}
    assert parse_for_download(args) == ["1", "2", "3"]

    # Mixed
    args = {"number": ["1,", "3-5"]}
    assert parse_for_download(args) == ["1", "3", "4", "5"]

    # Surprising behavior: eval is used for ranges
    args = {"number": ["1-2*3"]}
    assert parse_for_download(args) == ["1", "2", "3", "4", "5", "6"]

def test_parse_feed_info(tmp_path):
    # Prepare a history file
    history_file = tmp_path / "test_history"
    
    # Mix of JSON and old format
    json_entry = {"entrylink": "http://example.com/1", "linkdate": [2023, 1, 1, 0, 0, 0, 0, 0, 0]}
    old_entry = "http://example.com/2 [2023, 1, 2, 0, 0, 0, 0, 0, 0]"
    
    with open(history_file, "w") as f:
        f.write(json.dumps(json_entry) + "\n")
        f.write(old_entry + "\n")
        # This line is "invalid line\n". 
        # split(sep=' ') -> ['invalid', 'line\n']
        # eval('line\n') evaluates to the current value of the 'line' variable in parse_feed_info!
        f.write("invalid line\n") 

    links, dates = parse_feed_info(str(history_file))
    
    assert links == ["http://example.com/1", "http://example.com/2", "invalid"]
    assert dates == [
        [2023, 1, 1, 0, 0, 0, 0, 0, 0], 
        [2023, 1, 2, 0, 0, 0, 0, 0, 0],
        "invalid line\n"
    ]

def test_parse_feed_info_not_found():
    links, dates = parse_feed_info("non_existent_file")
    assert links == []
    assert dates == []

def test_get_date():
    from greg.aux_functions import get_date
    # JSON format
    json_line = '{"entrylink": "http://example.com/1", "linkdate": [2023, 1, 1, 0, 0, 0, 0, 0, 0]}'
    assert get_date(json_line) == [2023, 1, 1, 0, 0, 0, 0, 0, 0]
    
    # Old format
    old_line = "http://example.com/2 [2023, 1, 2, 0, 0, 0, 0, 0, 0]"
    assert get_date(old_line) == [2023, 1, 2, 0, 0, 0, 0, 0, 0]
    
    # Surprising behavior: eval can reference local variables or execute code
    # If the line is "anything line", eval("line") returns the current line
    assert get_date("anything line") == "anything line"
