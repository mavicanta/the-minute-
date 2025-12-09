import cv2
import time
import io
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler # We inherit from SimpleHTTPRequestHandler now
import socketserver
import os # Required for changing directory

# --- Configuration ---
HTTP_PORT = 8000
SERVER_HOST = "0.0.0.0" 
FRAME_DELAY = 0.033  # Approx 30 FPS (1/30)

# --- Define the folder to serve static client files from ---
HTTP_ROOT_DIR = "display" 

# --- Composite HTTP Request Handler (Inherits from SimpleHTTPRequestHandler) ---

class CustomRequestHandler(SimpleHTTPRequestHandler):
    """
    Handles both M-JPEG video stream requests and static file requests.
    Inheriting from SimpleHTTPRequestHandler gives us all file serving methods (like send_head).
    """
    
    def stream_video_feed(self):
        self.send_response(200)
        
        # CRITICAL FIX: Add CORS Header for Tainted Canvas fix
        self.send_header('Access-Control-Allow-Origin', '*') 
        
        self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--frameboundary')
        self.end_headers()

        cap = self.server.video_capture 
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Error: Failed to capture frame.")
                    break

                # Encode frame to JPEG format
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret: continue

                # Send M-JPEG stream boundary and headers
                self.wfile.write(b'--frameboundary\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(buffer)))
                self.end_headers()
                
                # Send the frame data
                self.wfile.write(buffer.tobytes())
                self.wfile.write(b'\r\n')
                
                time.sleep(FRAME_DELAY)

        except Exception as e:
            # Handle disconnected clients gracefully
            # print(f"Client disconnected or streaming error: {e}")
            pass

    def do_GET(self):
        if self.path == '/video_feed':
            # Serve the video stream
            self.stream_video_feed()
        else:
            # Delegate all static file requests (like /index-2.html) to the parent class.
            # This correctly calls the inherited file serving methods (like send_head).
            super().do_GET() 


# --- Main Server and Capture Setup ---

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Custom HTTPServer class to handle threads and store the video capture object."""
    def __init__(self, server_address, RequestHandlerClass, video_capture):
        super().__init__(server_address, RequestHandlerClass)
        self.video_capture = video_capture # Store the capture object

def run_server():
    # --- 1. Initialize Webcam ---
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # --- 2. Change Directory for File Serving ---
    try:
        # Move the script's working directory to the 'display' subfolder
        os.chdir(HTTP_ROOT_DIR)
        print(f"HTTP server root set to: {HTTP_ROOT_DIR}")
    except FileNotFoundError:
        print(f"Error: Directory '{HTTP_ROOT_DIR}' not found! Please create it and place your HTML file inside.")
        cap.release()
        return

    print("\n" + "="*50)
    print("M-JPEG Video Server Started!")
    print(f"File Server Root: {os.getcwd()}")
    print(f"Access Client: http://{SERVER_HOST}:{HTTP_PORT}/index-2.html")
    print(f"Stream URL: http://{SERVER_HOST}:{HTTP_PORT}/video_feed")
    print("="*50 + "\n")

    server_address = (SERVER_HOST, HTTP_PORT)
    
    # --- 3. Start Server ---
    # Use the custom handler that supports both video streaming and file serving
    httpd = ThreadedHTTPServer(server_address, CustomRequestHandler, cap)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        cap.release()
        print("Server and Webcam closed.")

if __name__ == "__main__":
    run_server()