from pytube import YouTube, request, extract
import webview
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from http.server import SimpleHTTPRequestHandler, HTTPServer
import threading

class RangeRequestHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        size = fs.st_size

        if "Range" in self.headers:
            self.send_response(206)
            start, end = self.headers['Range'].replace('bytes=', '').split('-')
            start = int(start)
            end = int(end) if end else size - 1
            if start >= size:
                self.send_error(416, "Requested Range Not Satisfiable")
                return None

            self.send_header("Content-type", ctype)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", end - start + 1)
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            f.seek(start)
            return f

        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

class DirectoryEventHandler(FileSystemEventHandler):
    def __init__(self, api):
        self.api = api

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".mp4"):
            print(f"Archivo creado: {event.src_path}")
            self.api.notify_change('created', event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(".mp4"):
            print(f"Archivo eliminado: {event.src_path}")
            self.api.notify_change('deleted', event.src_path)

class API:
    def __init__(self):
        self.lista = []
        self.on = True
        self.conf = {
            "ruta": os.path.expanduser("~/Videos/YT/")  # Asegurarse de usar la ruta correcta
        }
        self.progress_timer = None

        # Crear el directorio si no existe
        os.makedirs(self.conf["ruta"], exist_ok=True)

        # Configurar watchdog para monitorear el directorio
        self.event_handler = DirectoryEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.conf["ruta"], recursive=False)
        self.observer.start()

        # Iniciar servidor HTTP
        self.http_server = None
        self.start_http_server()

    def start_http_server(self):
        os.chdir(self.conf["ruta"])
        handler = RangeRequestHandler
        self.http_server = HTTPServer(("localhost", 8000), handler)
        thread = threading.Thread(target=self.http_server.serve_forever)
        thread.daemon = True
        thread.start()

    def notify_change(self, event_type, file_path):
        webview.windows[0].evaluate_js(f"""
            window.dispatchEvent(new CustomEvent('pywebview', {{
                detail: {{ 'type': '{event_type}', 'file': '{file_path}' }}
            }}));
        """)

    def progress_function(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining 
        percentage_of_completion = bytes_downloaded / total_size * 100
        print(f"Descargando: {percentage_of_completion:.2f}%")
        webview.windows[0].evaluate_js(f"""
            window.dispatchEvent(new CustomEvent('pywebview', {{
                detail: {{ 'type': 'progress', 'progress': '{percentage_of_completion:.2f}%' }}
            }}));
        """)

    def complete_function(self, stream, file_path):  
        webview.windows[0].evaluate_js(f"""
            window.dispatchEvent(new CustomEvent('pywebview', {{
                detail: {{ 'type': 'complete' }}
            }}));
        """)
        print("Descarga completada")

    def download_video(self, url: str, itag: int):
        video = YouTube(url, on_progress_callback=self.progress_function, on_complete_callback=self.complete_function)

        stream = video.streams.get_by_itag(itag)
        chosen_stream = stream

        if not video.title.endswith(".mp4"):
            video.title += ".mp4"

        chosen_stream.download(output_path=self.conf["ruta"], filename=video.title)

    def video_info(self, url: str):
        video = YouTube(url)
        file_path = f"http://localhost:8000/{video.title + '.mp4'}"
        info = {
            "id": extract.video_id(url),
            "title": video.title,
            "resolutions": self.get_qualitys(video),
            "path": file_path
        }
        return info

    def get_qualitys(self, video: str):
        calidades = [{"itag": stream.itag, "resolution": stream.resolution, "type": "video", "fileSize": stream.filesize_mb} if stream.resolution else {"itag": stream.itag, "type": "audio"} for stream in video.streams.filter(progressive=True)]
        return calidades

    def get_downloaded_videos(self):
        files = os.listdir(self.conf["ruta"])
        videos = [{"name": f, "path": f"http://localhost:8000/{f}"} for f in files if f.endswith(".mp4")]
        return videos

    def stop_observer(self):
        self.observer.stop()
        self.observer.join()
        if self.http_server:
            self.http_server.shutdown()

if __name__ == '__main__':
    api = API()
    try:
        webview.create_window('TubeLoader', 'http://127.0.0.1:5500/templates/index.html', js_api=api)
        webview.start(debug=True)
    except KeyboardInterrupt:
        api.stop_observer()
