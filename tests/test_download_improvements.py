import os
import errno
import pytest
from unittest.mock import MagicMock, patch, mock_open

from greg.classes import Session, Feed, Placeholders
import greg.aux_functions as aux

@patch('requests.get')
def test_successful_streamed_download(mock_get, tmp_path):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.iter_content.return_value = [b'chunk1', b'chunk2']
    mock_get.return_value = mock_response
    
    feed = MagicMock(spec=Feed)
    feed.retrieve_config.return_value = 'greg'
    
    placeholders = MagicMock(spec=Placeholders)
    placeholders.link = 'http://example.com/podcast.mp3'
    placeholders.filename = 'podcast.mp3'
    placeholders.directory = str(tmp_path)
    placeholders.fullpath = str(tmp_path / 'podcast.mp3')
    
    # Run download_handler
    with patch('os.path.isfile', return_value=False):
        with patch('builtins.open', mock_open()) as m_open:
            aux.download_handler(feed, placeholders)
            
            # Verify requests.get call
            mock_get.assert_called_once_with(placeholders.link, stream=True, timeout=30)
            
            # Verify file writing
            m_open.assert_called_once_with(placeholders.fullpath, 'wb')
            handle = m_open()
            handle.write.assert_any_call(b'chunk1')
            handle.write.assert_any_call(b'chunk2')

@patch('requests.get')
def test_enospc_during_download_cleanup(mock_get, tmp_path):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.iter_content.return_value = [b'chunk1', b'chunk2']
    mock_get.return_value = mock_response
    
    feed = MagicMock(spec=Feed)
    feed.retrieve_config.return_value = 'greg'
    
    fullpath = str(tmp_path / 'podcast.mp3')
    placeholders = MagicMock(spec=Placeholders)
    placeholders.link = 'http://example.com/podcast.mp3'
    placeholders.filename = 'podcast.mp3'
    placeholders.directory = str(tmp_path)
    placeholders.fullpath = fullpath
    
    # Simulate ENOSPC on write
    with patch('os.path.isfile', side_effect=[False, True]): # Second call True for cleanup check
        with patch('builtins.open', mock_open()) as m_open:
            handle = m_open()
            handle.write.side_effect = OSError(errno.ENOSPC, "No space left on device")
            
            with patch('os.remove') as mock_remove:
                with pytest.raises(OSError) as excinfo:
                    aux.download_handler(feed, placeholders)
                
                assert excinfo.value.errno == errno.ENOSPC
                # Verify cleanup
                mock_remove.assert_called_once_with(fullpath)

@patch('requests.get')
def test_enospc_during_download_cleanup_failure_not_masking(mock_get, tmp_path):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.iter_content.return_value = [b'chunk1']
    mock_get.return_value = mock_response
    
    feed = MagicMock(spec=Feed)
    feed.retrieve_config.return_value = 'greg'
    
    fullpath = str(tmp_path / 'podcast.mp3')
    placeholders = MagicMock(spec=Placeholders)
    placeholders.fullpath = fullpath
    placeholders.link = 'http://example.com/podcast.mp3'
    placeholders.filename = 'podcast.mp3'
    placeholders.directory = str(tmp_path)
    
    # Simulate ENOSPC on write
    with patch('os.path.isfile', side_effect=[False, True]):
        with patch('builtins.open', mock_open()) as m_open:
            handle = m_open()
            handle.write.side_effect = OSError(errno.ENOSPC, "No space left on device")
            
            # Simulate failure during cleanup
            with patch('os.remove', side_effect=OSError(errno.EPERM, "Permission denied")):
                with pytest.raises(OSError) as excinfo:
                    aux.download_handler(feed, placeholders)
                
                # Should still be ENOSPC, not EPERM
                assert excinfo.value.errno == errno.ENOSPC

@patch('greg.aux_functions.parse_podcast')
def test_enospc_stops_sync(mock_parse_podcast, tmp_path):
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
    
    # Two episodes
    e1 = MagicMock(title="Ep 1", link="http://ep1", published_parsed=(2023,1,1,0,0,0,0,0,0), updated_parsed=(2023,1,1,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep1.mp3", "type": "audio/mpeg"}], summary="")
    e2 = MagicMock(title="Ep 2", link="http://ep2", published_parsed=(2023,1,2,0,0,0,0,0,0), updated_parsed=(2023,1,2,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep2.mp3", "type": "audio/mpeg"}], summary="")
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
        # e1 fails with ENOSPC
        mock_dh.side_effect = OSError(errno.ENOSPC, "No space left on device")
        
        with patch('greg.aux_functions.filtercond', return_value=True):
            with patch('sys.stderr', new=MagicMock()):
                # We expect it to raise SystemExit or just stop. 
                # According to the requirement, it should stop processing.
                # If we catch ENOSPC in sync, we might just return.
                try:
                    sync(args)
                except OSError as e:
                    if e.errno != errno.ENOSPC:
                        raise
                except SystemExit:
                    pass
        
        # Verify e1 was attempted
        assert mock_dh.call_count == 1
        # Verify e2 was NOT attempted
        assert mock_dh.call_count < 2
        
        # Verify e1 recorded in failed file
        failed_log = data_dir / "failed"
        assert failed_log.exists()
        assert "Ep 1" in failed_log.read_text()

@patch('greg.aux_functions.parse_podcast')
def test_enospc_stops_sync_multiple_feeds(mock_parse_podcast, tmp_path):
    data_dir = tmp_path / "data_multi"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[feed1]\nurl=http://f1\n[feed2]\nurl=http://f2\n")
    
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "names": ["all"],
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
        # Fails on first download
        mock_dh.side_effect = OSError(errno.ENOSPC, "No space left on device")
        
        with patch('greg.aux_functions.filtercond', return_value=True):
            with patch('sys.stderr', new=MagicMock()):
                try:
                    sync(args)
                except SystemExit:
                    pass
        
        # Verify only one download attempted even if there are two feeds
        assert mock_dh.call_count == 1
        # Verify we stopped after first feed
        assert mock_parse_podcast.call_count == 1

@patch('greg.aux_functions.parse_podcast')
def test_ordinary_failure_continues_sync(mock_parse_podcast, tmp_path):
    data_dir = tmp_path / "data_ord"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[test_feed]\nurl=http://example.com/rss\n")
    
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "names": ["test_feed"],
        "downloaddirectory": str(tmp_path / "downloads"),
    }
    
    # Two episodes
    e1 = MagicMock(title="Ep 1", link="http://ep1", published_parsed=(2023,1,1,0,0,0,0,0,0), updated_parsed=(2023,1,1,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep1.mp3", "type": "audio/mpeg"}], summary="")
    e2 = MagicMock(title="Ep 2", link="http://ep2", published_parsed=(2023,1,2,0,0,0,0,0,0), updated_parsed=(2023,1,2,0,0,0,0,0,0), enclosures=[{"href": "http://example.com/ep2.mp3", "type": "audio/mpeg"}], summary="")
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
        # e1 fails with ordinary error, e2 succeeds
        mock_dh.side_effect = [Exception("Ordinary error"), None]
        
        with patch('greg.aux_functions.filtercond', return_value=True):
            with patch('sys.stderr', new=MagicMock()):
                sync(args)
        
        # Verify BOTH were attempted
        assert mock_dh.call_count == 2
        
        # Verify e1 recorded in failed file
        failed_log = data_dir / "failed"
        assert failed_log.exists()
        assert "Ep 1" in failed_log.read_text()
        assert "Ep 2" not in failed_log.read_text()
        
        # Verify e2 recorded in history
        history_file = data_dir / "test_feed"
        assert history_file.exists()
        assert "ep2.mp3" in history_file.read_text()

def test_enospc_stops_download_command(tmp_path):
    data_dir = tmp_path / "data_dl"
    data_dir.mkdir()
    data_file = data_dir / "data"
    data_file.write_text("[test_feed]\nurl=http://example.com/rss\n")
    
    # Create a real feeddump file
    import pickle
    dumpfilename = data_dir / "feeddump"
    dumpfilename.write_bytes(b"dummy")
    
    # Create simple objects that can be pickled
    class MockEntry:
        def __init__(self, title, link, enclosures):
            self.title = title
            self.link = link
            self.enclosures = enclosures
            self.linkdate = [2023, 1, 1, 0, 0, 0, 0, 0, 0]
        def get(self, key, default=None):
            return getattr(self, key, default)

    class MockPodcast:
        def __init__(self):
            self.entries = [
                MockEntry("Ep 1", "http://ep1", [{"href": "http://ep1.mp3", "type": "audio/mpeg"}]),
                MockEntry("Ep 2", "http://ep2", [{"href": "http://ep2.mp3", "type": "audio/mpeg"}])
            ]
            self.title = "Test Podcast"
            self.feed = MagicMock()
            self.feed.subtitle = "Subtitle"
            self.target = MagicMock()
            self.target.title = "Test Podcast"
            self.bozo = 0

    podcast_obj = MockPodcast()
    # We can't pickle MagicMocks, so we need to be careful.
    # Actually, let's just mock pickle.load and return what we want.
    
    args = {
        "configfile": None,
        "datadirectory": str(data_dir),
        "number": ["0,1"],
        "downloaddirectory": str(tmp_path / "downloads"),
        "mime": None,
        "downloadhandler": None
    }
    
    from greg.commands import download
    
    with patch('pickle.load', return_value=["test_feed", podcast_obj]):
        with patch('os.path.isfile', return_value=True): # For feeddump check
            with patch('greg.aux_functions.download_handler') as mock_dh:
                mock_dh.side_effect = OSError(errno.ENOSPC, "No space left on device")
                
                with patch('sys.stderr', new=MagicMock()):
                    try:
                        download(args)
                    except SystemExit:
                        pass
                
                assert mock_dh.call_count == 1
