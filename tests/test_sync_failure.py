import pytest
from unittest.mock import MagicMock, patch
import os
import sys
from greg.classes import Feed, Session

@patch('greg.aux_functions.parse_podcast')
def test_sync_aborts_on_download_failure(mock_parse_podcast, tmp_path):
    # Setup data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[test_feed]\nurl=http://example.com/rss\n")
    
    # Mock session
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "names": ["test_feed"],
        "downloaddirectory": str(tmp_path / "downloads"),
    }
    session = Session(args)
    
    # Create two mock entries
    entry1 = MagicMock()
    entry1.title = "Episode 1"
    entry1.link = "http://example.com/ep1"
    entry1.updated_parsed = (2023, 1, 1, 0, 0, 0, 0, 0, 0)
    entry1.published_parsed = (2023, 1, 1, 0, 0, 0, 0, 0, 0)
    entry1.enclosures = [{"href": "http://example.com/ep1.mp3", "type": "audio/mpeg"}]
    entry1.summary = "Summary 1"
    
    entry2 = MagicMock()
    entry2.title = "Episode 2"
    entry2.link = "http://example.com/ep2"
    entry2.updated_parsed = (2023, 1, 2, 0, 0, 0, 0, 0, 0)
    entry2.published_parsed = (2023, 1, 2, 0, 0, 0, 0, 0, 0)
    entry2.enclosures = [{"href": "http://example.com/ep2.mp3", "type": "audio/mpeg"}]
    entry2.summary = "Summary 2"
    
    mock_podcast = MagicMock()
    mock_podcast.title = "Test Podcast"
    mock_podcast.feed.published_parsed = (2023, 1, 2, 0, 0, 0, 0, 0, 0)
    mock_podcast.feed.subtitle = "Test Subtitle"
    mock_podcast.target.title = "Test Podcast"
    mock_podcast.entries = [entry1, entry2]
    mock_podcast.bozo = 0
    mock_parse_podcast.return_value = mock_podcast
    
    from greg.commands import sync
    
    # Mock download_handler to fail on first call and succeed on second
    with patch('greg.aux_functions.download_handler') as mock_dh:
        mock_dh.side_effect = [Exception("First download failed"), None]
        
        with patch('sys.stderr', new=MagicMock()) as mock_stderr:
            sync(args)
        
        # Should have called download_handler twice
        assert mock_dh.call_count == 2
        
        # Check history
        history_file = data_dir / "test_feed"
        assert history_file.exists()
        content = history_file.read_text()
        
        # ep1.mp3 should NOT be in history (failed)
        assert "ep1.mp3" not in content
        # ep2.mp3 SHOULD be in history (succeeded)
        assert "ep2.mp3" in content
        
        # Verify stderr was used
        assert mock_stderr.write.called

@patch('greg.aux_functions.parse_podcast')
def test_sync_continues_on_feed_failure(mock_parse_podcast, tmp_path):
    # Setup data directory with two feeds
    data_dir = tmp_path / "data_feeds"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[feed1]\nurl=http://example.com/rss1\n[feed2]\nurl=http://example.com/rss2\n")
    
    # Mock session
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "names": ["all"],
        "downloaddirectory": str(tmp_path / "downloads"),
    }
    
    # Mock entries for feed 1 (should fail) and feed 2 (should succeed)
    entry1 = MagicMock()
    entry1.title = "Feed 1 Episode"
    entry1.link = "http://example.com/f1e1"
    entry1.updated_parsed = (2023, 1, 1, 0, 0, 0, 0, 0, 0)
    entry1.published_parsed = (2023, 1, 1, 0, 0, 0, 0, 0, 0)
    entry1.enclosures = [{"href": "http://example.com/f1e1.mp3", "type": "audio/mpeg"}]
    entry1.summary = "Summary 1"
    
    entry2 = MagicMock()
    entry2.title = "Feed 2 Episode"
    entry2.link = "http://example.com/f2e1"
    entry2.updated_parsed = (2023, 1, 1, 0, 0, 0, 0, 0, 0)
    entry2.published_parsed = (2023, 1, 1, 0, 0, 0, 0, 0, 0)
    entry2.enclosures = [{"href": "http://example.com/f2e1.mp3", "type": "audio/mpeg"}]
    entry2.summary = "Summary 2"
    
    mock_podcast1 = MagicMock()
    mock_podcast1.title = "Feed 1"
    mock_podcast1.feed.published_parsed = (2023, 1, 1, 0, 0, 0, 0, 0, 0)
    mock_podcast1.feed.subtitle = "Subtitle 1"
    mock_podcast1.target.title = "Feed 1"
    mock_podcast1.entries = [entry1]
    mock_podcast1.bozo = 0
    
    mock_podcast2 = MagicMock()
    mock_podcast2.title = "Feed 2"
    mock_podcast2.feed.published_parsed = (2023, 1, 1, 0, 0, 0, 0, 0, 0)
    mock_podcast2.feed.subtitle = "Subtitle 2"
    mock_podcast2.target.title = "Feed 2"
    mock_podcast2.entries = [entry2]
    mock_podcast2.bozo = 0
    
    mock_parse_podcast.side_effect = [mock_podcast1, mock_podcast2]
    
    from greg.commands import sync
    
    with patch('greg.aux_functions.download_handler') as mock_dh:
        # First download fails, second should still happen
        mock_dh.side_effect = [Exception("Feed 1 download failed"), None]
        
        with patch('sys.stderr', new=MagicMock()) as mock_stderr:
            sync(args)
        
        assert mock_dh.call_count == 2
        assert mock_dh.call_args_list[0][0][1].filename == "f1e1.mp3"
        assert mock_dh.call_args_list[1][0][1].filename == "f2e1.mp3"

@patch('greg.aux_functions.parse_podcast')
def test_failed_log_functionality(mock_parse_podcast, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[test_feed]\nurl=http://example.com/rss\n")
    
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "names": ["test_feed"],
        "downloaddirectory": str(tmp_path / "downloads"),
    }
    
    # Episode 1 fails, Episode 2 filtered, Episode 3 succeeds
    e1 = MagicMock(title="Ep 1", link="http://ep1", published_parsed=(2023,1,1,0,0,0,0,0,0), updated_parsed=(2023,1,1,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep1.mp3", "type": "audio/mpeg"}], summary="")
    e2 = MagicMock(title="Ep 2", link="http://ep2", published_parsed=(2023,1,2,0,0,0,0,0,0), updated_parsed=(2023,1,2,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep2.mp3", "type": "audio/mpeg"}], summary="")
    e3 = MagicMock(title="Ep 3", link="http://ep3", published_parsed=(2023,1,3,0,0,0,0,0,0), updated_parsed=(2023,1,3,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep3.mp3", "type": "audio/mpeg"}], summary="")
    e1.get.return_value = None
    e2.get.return_value = None
    e3.get.return_value = None

    mock_podcast = MagicMock(title="Test Feed")
    mock_podcast.feed.published_parsed = (2023,1,3,0,0,0,0,0,0)
    mock_podcast.feed.subtitle = ""
    mock_podcast.target.title = "Test Feed"
    mock_podcast.entries = [e1, e2, e3]
    mock_podcast.bozo = 0
    mock_parse_podcast.return_value = mock_podcast

    from greg.commands import sync
    
    with patch('greg.aux_functions.download_handler') as mock_dh:
        # e1 fails, e3 succeeds (e2 is filtered)
        mock_dh.side_effect = [Exception("Download failed"), None]
        
        # Mock filtercond: e1 True, e2 False, e3 True
        with patch('greg.aux_functions.filtercond') as mock_filter:
            mock_filter.side_effect = [True, False, True]
            
            with patch('sys.stderr', new=MagicMock()):
                sync(args)
    
    failed_log = data_dir / "failed"
    assert failed_log.exists()
    content = failed_log.read_text()
    
    # Ep 1 should be in log
    assert "test_feed\tEp 1\thttp://example.com/ep1.mp3" in content
    # Ep 2 (filtered) should NOT be in log
    assert "Ep 2" not in content
    # Ep 3 (succeeded) should NOT be in log
    assert "Ep 3" not in content

    # Test clearing log on next sync
    with patch('greg.aux_functions.download_handler') as mock_dh:
        mock_dh.side_effect = [None, None, None]
        with patch('greg.aux_functions.filtercond', return_value=True):
            with patch('sys.stderr', new=MagicMock()):
                sync(args)
    
    # Log should be cleared (removed) because second sync had no failures
    assert not failed_log.exists()

@patch('greg.aux_functions.parse_podcast')
def test_failed_log_deduplication(mock_parse_podcast, tmp_path):
    data_dir = tmp_path / "data_dedup"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[test_feed]\nurl=http://example.com/rss\n")
    
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "names": ["test_feed"],
        "downloaddirectory": str(tmp_path / "downloads"),
    }
    
    # Two episodes with DIFFERENT titles but SAME enclosure URL
    e1 = MagicMock(title="Ep 1", link="http://ep1", published_parsed=(2023,1,1,0,0,0,0,0,0), updated_parsed=(2023,1,1,0,0,0,0,0,0), summary="")
    e2 = MagicMock(title="Ep 2", link="http://ep2", published_parsed=(2023,1,2,0,0,0,0,0,0), updated_parsed=(2023,1,2,0,0,0,0,0,0), summary="")
    e1.get.return_value = None
    e2.get.return_value = None
    e1.enclosures = [{"href": "http://example.com/same.mp3", "type": "audio/mpeg"}]
    e2.enclosures = [{"href": "http://example.com/same.mp3", "type": "audio/mpeg"}]

    mock_podcast = MagicMock(title="Test Feed")
    mock_podcast.feed.published_parsed = (2023,1,2,0,0,0,0,0,0)
    mock_podcast.feed.subtitle = ""
    mock_podcast.target.title = "Test Feed"
    mock_podcast.entries = [e1, e2]
    mock_podcast.bozo = 0
    mock_parse_podcast.return_value = mock_podcast

    from greg.commands import sync
    
    with patch('greg.aux_functions.download_handler') as mock_dh:
        # Both fail
        mock_dh.side_effect = [Exception("Fail 1"), Exception("Fail 2")]
        
        with patch('greg.aux_functions.filtercond', return_value=True):
            with patch('sys.stderr', new=MagicMock()):
                sync(args)
    
    failed_log = data_dir / "failed"
    content = failed_log.read_text()
    
    # Should only have ONE entry in the failed log because the URL is the same
    assert content.count("http://example.com/same.mp3") == 1
    # It should have recorded the first one
    assert "Ep 1" in content
    assert "Ep 2" not in content

@patch('greg.aux_functions.parse_podcast')
def test_failed_log_uses_url_not_title_for_identity(mock_parse_podcast, tmp_path):
    data_dir = tmp_path / "data_id"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[test_feed]\nurl=http://example.com/rss\n")
    
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "names": ["test_feed"],
        "downloaddirectory": str(tmp_path / "downloads"),
    }
    
    # Two episodes with SAME title but DIFFERENT links
    e1 = MagicMock(title="Same Title", link="http://ep1", published_parsed=(2023,1,1,0,0,0,0,0,0), updated_parsed=(2023,1,1,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep1.mp3", "type": "audio/mpeg"}], summary="")
    e2 = MagicMock(title="Same Title", link="http://ep2", published_parsed=(2023,1,2,0,0,0,0,0,0), updated_parsed=(2023,1,2,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep2.mp3", "type": "audio/mpeg"}], summary="")
    e1.get.return_value = None
    e2.get.return_value = None

    mock_podcast = MagicMock(title="Test Feed")
    mock_podcast.feed.published_parsed = (2023,1,2,0,0,0,0,0,0)
    mock_podcast.feed.subtitle = ""
    mock_podcast.target.title = "Test Feed"
    mock_podcast.entries = [e1, e2]
    mock_podcast.bozo = 0
    mock_parse_podcast.return_value = mock_podcast

    from greg.commands import sync
    
    with patch('greg.aux_functions.download_handler') as mock_dh:
        mock_dh.side_effect = [Exception("Fail 1"), Exception("Fail 2")]
        with patch('greg.aux_functions.filtercond', return_value=True):
            with patch('sys.stderr', new=MagicMock()):
                sync(args)
    
    failed_log = data_dir / "failed"
    content = failed_log.read_text()
    
    # BOTH should be in the log because they have different URLs
    assert content.count("Same Title") == 2
    assert "http://example.com/ep1.mp3" in content
    assert "http://example.com/ep2.mp3" in content

@patch('greg.aux_functions.parse_podcast')
def test_tagging_failure_does_not_mark_as_failed_download(mock_parse_podcast, tmp_path):
    data_dir = tmp_path / "data_tag"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[test_feed]\nurl=http://example.com/rss\n")
    
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "names": ["test_feed"],
        "downloaddirectory": str(tmp_path / "downloads"),
    }
    
    e1 = MagicMock(title="Ep 1", link="http://ep1", published_parsed=(2023,1,1,0,0,0,0,0,0), updated_parsed=(2023,1,1,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep1.mp3", "type": "audio/mpeg"}], summary="")
    e1.get.return_value = None

    mock_podcast = MagicMock(title="Test Feed")
    mock_podcast.feed.published_parsed = (2023,1,1,0,0,0,0,0,0)
    mock_podcast.feed.subtitle = ""
    mock_podcast.target.title = "Test Feed"
    mock_podcast.entries = [e1]
    mock_podcast.bozo = 0
    mock_parse_podcast.return_value = mock_podcast

    from greg.commands import sync
    
    with patch('greg.aux_functions.download_handler') as mock_dh:
        with patch('greg.aux_functions.tag') as mock_tag:
            with patch('greg.classes.Feed.will_tag', return_value=True):
                mock_dh.return_value = None
                mock_tag.side_effect = Exception("Tagging failed")
                
                with patch('sys.stderr', new=MagicMock()) as mock_stderr:
                    sync(args)
                
                # Ep 1 SHOULD be in history because download succeeded
                history_file = data_dir / "test_feed"
                assert history_file.exists()
                content = history_file.read_text()
                assert "ep1.mp3" in content
                
                # Failed log SHOULD NOT have it
                failed_log = data_dir / "failed"
                assert not failed_log.exists()
                
                # Stderr should report tagging failure
                tag_error_reported = any("Failed to tag" in str(call) for call in mock_stderr.write.call_args_list)
                assert tag_error_reported

if __name__ == "__main__":
    # This is to run it easily
    pytest.main([__file__])
