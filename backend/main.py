from pathlib import Path
from datetime import datetime
import platform

import cv2


# ============================================================
# DETECT PLATFORM
# ============================================================

IS_WINDOWS = platform.system() == "Windows"

# Picamera2 is only imported on Raspberry Pi
if not IS_WINDOWS:
    try:
        from picamera2 import Picamera2
        PICAMERA2_AVAILABLE = True
    except ImportError:
        Picamera2 = None
        PICAMERA2_AVAILABLE = False
else:
    Picamera2 = None
    PICAMERA2_AVAILABLE = False


class Camera:

    def __init__(self):

        self.picam2 = None
        self.cap = None
        self.started = False

        # =====================================================
        # CAMERA STORAGE
        # =====================================================

        project_dir = Path(__file__).resolve().parent.parent

        self.storage_dir = project_dir / "camera_data"
        self.photo_dir = self.storage_dir / "photos"
        self.video_dir = self.storage_dir / "videos"

        self.photo_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================
    # CAMERA INFO
    # Keeps existing main.py working
    # =========================================================

    class CameraInfo:

        def __init__(self, camera):
            self.camera = camera

        def get(self, property_id):

            # -------------------------
            # WINDOWS WEBCAM
            # -------------------------

            if IS_WINDOWS:

                if self.camera.cap is None:
                    return 0

                try:
                    return self.camera.cap.get(property_id)
                except Exception:
                    return 0

            # -------------------------
            # RASPBERRY PI CAMERA
            # -------------------------

            if self.camera.picam2 is None:
                return 0

            if property_id == cv2.CAP_PROP_FRAME_WIDTH:
                return 1280

            if property_id == cv2.CAP_PROP_FRAME_HEIGHT:
                return 720

            if property_id == cv2.CAP_PROP_FPS:
                return 30

            return 0

        def isOpened(self):

            if IS_WINDOWS:

                return (
                    self.camera.cap is not None
                    and self.camera.cap.isOpened()
                )

            return self.camera.started

        def release(self):
            self.camera.stop()

    # =========================================================
    # START CAMERA
    # =========================================================

    def start(self, index=0):

        try:

            print("================================")
            print("STARTING CAMERA")
            print("================================")

            if self.started:
                return True

            # =================================================
            # WINDOWS
            # =================================================

            if IS_WINDOWS:

                print("MODE: WINDOWS WEBCAM")

                self.cap = cv2.VideoCapture(index)

                if not self.cap.isOpened():

                    print("ERROR: Laptop webcam could not be opened")

                    self.cap = None
                    self.started = False

                    return False

                # Request 1280x720
                self.cap.set(
                    cv2.CAP_PROP_FRAME_WIDTH,
                    1280
                )

                self.cap.set(
                    cv2.CAP_PROP_FRAME_HEIGHT,
                    720
                )

                self.cap.set(
                    cv2.CAP_PROP_FPS,
                    30
                )

                self.started = True

                print("LAPTOP WEBCAM STARTED")
                print("Resolution: 1280 x 720")
                print("FPS: 30")

                return True

            # =================================================
            # RASPBERRY PI
            # =================================================

            print("MODE: RASPBERRY PI")

            if not PICAMERA2_AVAILABLE:

                print("ERROR: Picamera2 is not available")

                return False

            print("STARTING PICAMERA2")

            self.picam2 = Picamera2()

            # IMPORTANT:
            # This is the simple configuration that was
            # successfully tested with your IMX708.
            #
            # Picamera2 automatically selects:
            # 1280x720-XBGR8888
            #
            # We convert the 4-channel image to BGR
            # inside read() below.

            config = self.picam2.create_video_configuration()

            self.picam2.configure(config)

            self.picam2.start()

            self.started = True

            self.cap = self.CameraInfo(self)

            print("IMX708 CAMERA STARTED")
            print("Resolution: 1280 x 720")
            print("FPS: 30")

            return True

        except Exception as e:

            print("CAMERA START ERROR:")
            print(e)

            self.picam2 = None
            self.cap = None
            self.started = False

            return False

    # =========================================================
    # READ FRAME
    # =========================================================

    def read(self):

        if not self.started:
            return None

        try:

            # =================================================
            # WINDOWS
            # =================================================

            if IS_WINDOWS:

                if self.cap is None:
                    return None

                ret, frame = self.cap.read()

                if not ret:
                    return None

                return frame

            # =================================================
            # RASPBERRY PI
            # =================================================

            if self.picam2 is None:
                return None

            frame = self.picam2.capture_array("main")

            if frame is None:
                return None

            # Picamera2's working configuration returns
            # XBGR8888 = 4 channels.
            #
            # Existing main.py expects a normal 3-channel
            # BGR OpenCV image.

            if frame.ndim == 3:

                if frame.shape[2] == 4:

                    frame = cv2.cvtColor(
                        frame,
                        cv2.COLOR_BGRA2BGR
                    )

            return frame

        except Exception as e:

            print("CAMERA READ ERROR:")
            print(e)

            return None

    # =========================================================
    # CAPTURE PHOTO
    # =========================================================

    def capture(self, filename="capture.jpg"):

        if not self.started:

            print("Camera is not running")

            return False

        try:

            frame = self.read()

            if frame is None:
                return False

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            output_file = self.photo_dir / (
                f"photo_{timestamp}.jpg"
            )

            success = cv2.imwrite(
                str(output_file),
                frame
            )

            if success:

                print("================================")
                print("PHOTO CAPTURED")
                print("Saved:", output_file)
                print("================================")

                return True

            print("Photo save failed")

            return False

        except Exception as e:

            print("PHOTO CAPTURE ERROR:")
            print(e)

            return False

    # =========================================================
    # STANDALONE PREVIEW
    # =========================================================

    def preview(self):

        if not self.started:

            if not self.start():
                return

        print("Camera preview started")
        print("Press Q to quit")

        try:

            while self.started:

                frame = self.read()

                if frame is None:
                    break

                cv2.imshow(
                    "Segway Camera",
                    frame
                )

                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break

        finally:

            self.stop()

    # =========================================================
    # STOP CAMERA
    # =========================================================

    def stop(self):

        print("Stopping camera...")

        self.started = False

        # =====================================================
        # WINDOWS
        # =====================================================

        if IS_WINDOWS:

            if self.cap is not None:

                try:
                    self.cap.release()
                except Exception:
                    pass

            self.cap = None

            cv2.destroyAllWindows()

            print("Camera stopped")

            return

        # =====================================================
        # RASPBERRY PI
        # =====================================================

        if self.picam2 is not None:

            try:
                self.picam2.stop()
            except Exception:
                pass

            try:
                self.picam2.close()
            except Exception:
                pass

        self.picam2 = None
        self.cap = None

        cv2.destroyAllWindows()

        print("Camera stopped")

    # =========================================================
    # CAMERA STATUS
    # =========================================================

    def is_open(self):

        return self.started