from http.server import HTTPServer, SimpleHTTPRequestHandler
import os


HOST = "localhost"
PORT = 8000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class CustomHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # 1. Map root URL to static/welcome.html
        if self.path == "/":
            self.path = "/static/welcome.html"

        elif self.path == "/welcome":
            self.path = "/static/welcome.html"

        elif self.path.startswith(("/css/", "/js/", "/assets/")):
            self.path = "/static" + self.path

        elif self.path == "/lab":
            self.path = "/static/lab.html"

        elif self.path.startswith("/static/"):
            pass

        else:
            self.path = "/static/page404.html"

        return super().do_GET()

    
def main():

    os.chdir(BASE_DIR)
    server = HTTPServer(
        (HOST, PORT),
        CustomHandler
    )

    print(f"Cyber Hazard Lab running at http://{HOST}:{PORT}")

    try:
        server.serve_forever()


    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()