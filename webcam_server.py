import cv2
import asyncio
import websockets
import json
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
import socketserver
import threading 

# --- Configuration ---
HTTP_PORT = 8000
WS_PORT = 8765
LATEST_IMAGE_FILENAME = "captured_latest.jpg" 
SERVER_HOST = "localhost" # Use "0.0.0.0" if connecting from another device

# Store connected clients
connected_clients = set()

# --- WebSocket Handlers ---

async def handle_client(websocket):
    """Handle new WebSocket connections"""
    connected_clients.add(websocket)
    print(f"Client connected. Total clients: {len(connected_clients)}")
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        print(f"Client disconnected. Total clients: {len(connected_clients)}")

async def send_notification_to_clients():
    """Send a notification to all connected clients to reload the image."""
    if connected_clients:
        message = json.dumps({
            'type': 'new_image_ready',
            'filename': LATEST_IMAGE_FILENAME,
            'timestamp': datetime.now().isoformat()
        })
        # Use asyncio.gather to send the small message concurrently
        await asyncio.gather(
            *[client.send(message) for client in connected_clients],
            return_exceptions=True
        )

# --- HTTP Server Thread ---

def start_http_server():
    """Starts a simple HTTP server in a separate thread."""
    # This handler serves files from the current directory
    Handler = SimpleHTTPRequestHandler
    
    # Use threading so the HTTP server doesn't block asyncio
    with socketserver.TCPServer(("", HTTP_PORT), Handler) as httpd:
        print(f"HTTP Server serving files on port {HTTP_PORT}")
        # httpd.serve_forever() is blocking, but it's in a thread
        httpd.serve_forever()

# --- Main Webcam Loop ---

async def webcam_loop():
    """Main webcam capture loop"""
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Camera 0 not available, trying camera 1...")
        cap = cv2.VideoCapture(1)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    # Set resolution for good quality display
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    window_name = 'Webcam - Press S to capture, Q to quit'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    print("\n" + "="*50)
    print("Webcam Server Started!")
    print(f"WS Server: ws://{SERVER_HOST}:{WS_PORT}")
    print(f"HTTP Server: http://{SERVER_HOST}:{HTTP_PORT}")
    print("="*50)
    print("Controls:")
    print("  Press 'S' - Capture, save, and notify client to load image")
    print("  Press 'F' - Toggle fullscreen")
    print("  Press 'Q' - Quit")
    print("="*50 + "\n")
    
    fullscreen = False
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("Error: Failed to capture frame")
            break
        
        # Display preview
        display_frame = frame.copy()
        cv2.putText(display_frame, "Press 'S' to capture and send notification", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow(window_name, display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q') or key == 27:
            break
        
        elif key == ord('s'):
            # 1. Save locally with the consistent filename
            cv2.imwrite(LATEST_IMAGE_FILENAME, frame) 

            # 2. Send only a small notification, not the image data
            await send_notification_to_clients()
            
            print(f"✓ Picture captured and saved as {LATEST_IMAGE_FILENAME}")
            print(f"  Sent notification to {len(connected_clients)} client(s)")
        
        elif key == ord('f'):
            fullscreen = not fullscreen
            if fullscreen:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, 
                                     cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, 
                                     cv2.WINDOW_NORMAL)
        
        await asyncio.sleep(0.01)
    
    cap.release()
    cv2.destroyAllWindows()
    print("Webcam closed")

# --- Main Execution ---

async def main():
    """Start WebSocket server, HTTP server, and webcam loop"""
    
    # Start HTTP server in a non-blocking thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Start WebSocket server
    async with websockets.serve(handle_client, SERVER_HOST, WS_PORT):
        print(f"WebSocket server started on ws://{SERVER_HOST}:{WS_PORT}")
        # Run webcam loop (this will block until quit)
        await webcam_loop()

if __name__ == "__main__":
    asyncio.run(main())