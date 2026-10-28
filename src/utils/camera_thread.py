import threading
import time
import cv2
from pyzbar import pyzbar
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage


class CameraThread(QThread):
    frame_processed = Signal(QImage)
    frame_received = Signal(QImage, object)
    qr_detected = Signal(str)
    status_changed = Signal(str)

    def __init__(self, camera_index: int = 0, target_fps: int = 30, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.target_fps = target_fps
        self._is_running = True
        self._scanning_paused = False
        self._frame_skip_counter = 0
        # Guards all access to self.cap — cv2.VideoCapture is NOT thread-safe, and
        # resume_scanning()/_flush_hardware_buffer() can be called from the GUI thread
        # while run() is concurrently calling cap.read() on the worker thread.
        self._cap_lock = threading.Lock()

    def pause_scanning(self):
        self._scanning_paused = True

    def resume_scanning(self):
        """Flushes stale OpenCV video buffer captured while modal was open."""
        self._flush_hardware_buffer()
        self._scanning_paused = False

    def _flush_hardware_buffer(self):
        with self._cap_lock:
            if hasattr(self, 'cap') and self.cap.isOpened():
                # Perform rapid non-decoding grabs to clear driver frame queue
                for _ in range(5):
                    self.cap.grab()

    def run(self):
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if self.cap.isOpened():
            self.status_changed.emit("Camera Active • Scanning")
        else:
            self.status_changed.emit("Camera Hardware Offline")

        while self._is_running:
            with self._cap_lock:
                ret, frame = self.cap.read()

            if not ret:
                time.sleep(0.01)
                continue

            # Convert BGR to RGB for rendering without heap allocations
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w

            # .copy() forces a deep copy of the pixel buffer into QImage's own
            # internal storage. Without it, QImage merely wraps rgb_frame's numpy
            # buffer by raw pointer; since frame_received is a queued cross-thread
            # signal, the GUI thread may not paint this QImage until after rgb_frame
            # has already been garbage-collected/reused on the next loop iteration,
            # causing corrupted frames or a use-after-free crash.
            q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            self.frame_received.emit(q_img, frame)

            # Evaluate QR decode every 2nd frame when active
            self._frame_skip_counter += 1
            if not self._scanning_paused and (self._frame_skip_counter % 2 == 0):
                # Optimize decoding: convert to single-channel grayscale (8-bit)
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                barcodes = pyzbar.decode(gray_frame)

                for barcode in barcodes:
                    qr_data = barcode.data.decode("utf-8").strip()
                    if qr_data:
                        self.qr_detected.emit(qr_data)
                        self.pause_scanning()
                        break

            time.sleep(0.015)  # Yield CPU execution slice

        with self._cap_lock:
            self.cap.release()

    def stop(self):
        self._is_running = False
        self.wait()