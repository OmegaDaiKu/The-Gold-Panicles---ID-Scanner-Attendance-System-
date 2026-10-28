from unittest.mock import MagicMock, patch
from src.utils.camera_thread import CameraThread


def test_camera_thread_pause_and_resume():
    thread = CameraThread(camera_index=0)
    thread.cap = MagicMock()
    thread.cap.isOpened.return_value = True

    # Pause scanning
    thread.pause_scanning()
    assert thread._scanning_paused is True

    # Resume scanning should invoke cap.grab() buffer flush
    thread.resume_scanning()
    assert thread._scanning_paused is False
    assert thread.cap.grab.call_count == 5