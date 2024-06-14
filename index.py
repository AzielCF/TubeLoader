from pytube import YouTube, request, extract
import webview
import os

class API:
    def __init__(self):
        self.lista = []
        self.on = True
        self.conf = {
            "ruta": os.path.expandvars("%USERPROFILE%/Videos/YT/")
        }
        self.progress_timer = None

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

    def donwload_video(self, url: str,  itag: int):
        video = YouTube(url, on_progress_callback=self.progress_function, on_complete_callback=self.complete_function)
        print(request.filesize(url))

        stream = video.streams.get_by_itag(itag)
        chosen_stream = stream

        if not video.title.endswith(".mp4"):
            video.title += ".mp4"

        chosen_stream.download(output_path=self.conf["ruta"], filename=video.title)
    
    def video_info(self, url: str):
        video = YouTube(url)
        info = {"id": extract.video_id(url), "title": video.title, "resolutions": self.obtener_calidades(video) }
        return info

    def obtener_calidades(self, video: str):
        calidades = [{"itag": stream.itag, "resolution": stream.resolution, "type": "video", "fileSize": stream.filesize_mb} if stream.resolution else {"itag": stream.itag, "type": "audio"} for stream in video.streams.filter(progressive=True)]
        return calidades

if __name__ == '__main__':
    # Crear una ventana con PyWebView y apuntar a la URL del servidor Flask
    webview.create_window('TubeLoader', 'http://127.0.0.1:5500/templates/index.html', js_api=API())
    webview.start(debug=True)
