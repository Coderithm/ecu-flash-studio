
import http.server
import socketserver
import webbrowser
import threading
import sys
import socket
import json
import time
import urllib.parse

from core.api_routes import get_flash_status, start_multiflash, read_nvm, write_nvm, get_nvm_map, update_nvm_map
from frontend.html_core import HTML_WRAPPER
from frontend.module_utils import UTILS_JSX
from frontend.module_sidebar import SIDEBAR_JSX
from frontend.module_dashboard import DASHBOARD_JSX
from frontend.module_multiflash import MULTIFLASH_JSX
from frontend.module_nvm import NVM_JSX
from frontend.module_flashlog import FLASHLOG_JSX
from frontend.module_interruptions import INTERRUPTIONS_JSX
from frontend.module_cantrace import CANTRACE_JSX
from frontend.module_app import APP_JSX

# Dynamically construct the application payload
PAYLOAD = f"{UTILS_JSX}\n{SIDEBAR_JSX}\n{DASHBOARD_JSX}\n{MULTIFLASH_JSX}\n{NVM_JSX}\n{FLASHLOG_JSX}\n{INTERRUPTIONS_JSX}\n{CANTRACE_JSX}\n{APP_JSX}"
GENERATED_HTML = HTML_WRAPPER.replace("{CONTENT}", PAYLOAD)

class PurePythonRouter(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/flash_status':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_flash_status()).encode("utf-8"))
            return
        elif parsed.path == '/api/nvm_read':
            qs = urllib.parse.parse_qs(parsed.query)
            did = qs.get('did', [''])[0]
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(read_nvm(did)).encode("utf-8"))
            return
        elif parsed.path == '/api/nvm_map':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": get_nvm_map()}).encode("utf-8"))
            return
        elif parsed.path == '/api/can_trace':
            import core.api_routes
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"trace": core.api_routes.can_trace_log}).encode("utf-8"))
            return
        elif parsed.path == '/api/ecu_config':
            from core.api_routes import get_ecu_config
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_ecu_config()).encode("utf-8"))
            return
        elif parsed.path == '/api/ecu_read_sw':
            from core.api_routes import read_sw_version
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(read_sw_version()).encode("utf-8"))
            return
        elif parsed.path == '/api/export_trc':
            from core.api_routes import export_trc
            trc_content = export_trc()
            if trc_content is None:
                self.send_response(204)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-type", "application/octet-stream")
            self.send_header("Content-Disposition", "attachment; filename=flash_trace.trc")
            self.end_headers()
            self.wfile.write(trc_content.encode("utf-8"))
            return
        elif self.path.startswith('/static/'):
            return super().do_GET()
        
        # Route ALL valid standard paths to the Python-generated UI
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(GENERATED_HTML.encode("utf-8"))
        
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/start_multiflash':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            files = payload.get('files', [])
            times = payload.get('times', 1)
            
            start_multiflash(files, times)
                
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode("utf-8"))
            return
        elif parsed.path == '/api/nvm_write':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            did = payload.get('did', '')
            data = payload.get('data', [])
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(write_nvm(did, data)).encode("utf-8"))
            return
        elif parsed.path == '/api/nvm_map_write':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            addr = payload.get('address', '')
            val = payload.get('value', '')
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(update_nvm_map(addr, val)).encode("utf-8"))
            return
        elif parsed.path == '/api/run_interruption_test':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            test_id = payload.get('test_id')
            from core.api_routes import start_interruption_test
            started = start_interruption_test(test_id)
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"started": started}).encode("utf-8"))
            return
        elif parsed.path == '/api/can_trace_clear':
            import core.api_routes
            core.api_routes.clear_trace()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "cleared"}).encode("utf-8"))
            return

    def log_message(self, format, *args):
        pass

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true", help="Force open in browser instead of native window")
    args = parser.parse_args()

    port = get_free_port()
    httpd = socketserver.TCPServer(("", port), PurePythonRouter)
    
    print(f"[*] Starting Pure-Python Engine on port {port}...")
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    url = f"http://localhost:{port}"

    use_webview = not args.browser
    if use_webview:
        try:
            import webview
        except ImportError:
            print("[*] pywebview not installed, falling back to browser mode.")
            print("[*] Install with: pip install pywebview")
            use_webview = False

    if use_webview:
        print(f"[*] Opening native desktop window...")
        window = webview.create_window(
            "ECU Flash Tool — Diagnostic & Flash Studio",
            url,
            width=1280,
            height=820,
            min_size=(960, 600),
            background_color="#020617",
            text_select=True,
        )
        webview.start()
        print("\n[*] Window closed. Shutting down server...")
        httpd.shutdown()
        httpd.server_close()
        sys.exit(0)
    else:
        print(f"[*] Opening browser to {url}")
        webbrowser.open(url)
        print("[*] Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] Shutting down server...")
            httpd.shutdown()
            httpd.server_close()
            sys.exit(0)
