"""
Signadji - Serveur local avec API pour accéder aux PDFs réseau.
Usage: python server.py
"""

import http.server
import json
import os
import socketserver
import threading
import urllib.parse
from pathlib import Path

PORT = 8080
PDF_ROOT = os.environ.get("PDF_ROOT", "/mnt/pdfs")
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
YEARS = ["2024", "2025", "2026"]


class SigandjiHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path.startswith("/api/save/"):
            self.handle_save_pdf(path)
        else:
            self.send_error(404, "Endpoint introuvable")

    def handle_save_pdf(self, path):
        # /api/save/<year>/<filename>
        parts = path.split("/", 4)  # ['', 'api', 'save', 'year', 'filename']
        if len(parts) < 5:
            self.send_error(400, "Format attendu: /api/save/<year>/<filename>")
            return
        year = parts[3]
        filename = parts[4]
        if year not in YEARS:
            self.send_error(400, "Année invalide")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_error(400, "Aucun contenu reçu")
            return

        body = self.rfile.read(content_length)
        folder = os.path.join(PDF_ROOT, year)
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)

        with open(filepath, "wb") as f:
            f.write(body)

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "ok": True,
            "path": filepath,
        }, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path == "/index.html":
            self.send_response(301)
            self.send_header("Location", "/")
            self.end_headers()
        elif path == "/api/files":
            self.handle_list_files()
        elif path.startswith("/api/pdf/"):
            self.handle_serve_pdf(path)
        else:
            super().do_GET()

    def handle_list_files(self):
        files = []
        for year in YEARS:
            folder = os.path.join(PDF_ROOT, year)
            if not os.path.isdir(folder):
                continue
            for entry in os.scandir(folder):
                if entry.is_file() and entry.name.lower().endswith(".pdf"):
                    stat = entry.stat()
                    files.append({
                        "name": entry.name,
                        "year": year,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })
        files.sort(key=lambda f: f["name"].lower())
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(files, ensure_ascii=False).encode("utf-8"))

    def handle_serve_pdf(self, path):
        # /api/pdf/<year>/<filename>
        parts = path.split("/", 4)  # ['', 'api', 'pdf', 'year', 'filename']
        if len(parts) < 5:
            self.send_error(400, "Format attendu: /api/pdf/<year>/<filename>")
            return
        year = parts[3]
        filename = parts[4]
        if year not in YEARS:
            self.send_error(404, "Année invalide")
            return
        filepath = os.path.join(PDF_ROOT, year, filename)
        if not os.path.isfile(filepath):
            self.send_error(404, "Fichier introuvable")
            return
        stat = os.stat(filepath)
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header("Content-Disposition", f'inline; filename="{urllib.parse.quote(filename)}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(filepath, "rb") as f:
            self.wfile.write(f.read())

    def log_message(self, format, *args):
        # Quieter logging — only show API calls
        if "/api/" in str(args[0]):
            super().log_message(format, *args)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    with ThreadedHTTPServer(("", PORT), SigandjiHandler) as httpd:
        print(f"Signadji server running on http://localhost:{PORT}")
        print(f"PDF source: {PDF_ROOT}")
        httpd.serve_forever()
