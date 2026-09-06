
import sys
import os

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

sys.path.insert(0, BASE_DIR)
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json

from backend.orchestrator import Simulation
from application.ntm.ntm import NetworkTopologyManager
from application.ncm.ncm import NetworkConfigurationManager
from application.api import API


HOST = "localhost"
PORT = 8000


simulation = Simulation()

ntm = NetworkTopologyManager(simulation)
ncm = NetworkConfigurationManager(simulation)

api = API(ntm, ncm)

class CustomHandler(SimpleHTTPRequestHandler):
    def do_GET(self):

        if self.path.startswith("/api/"):
            try:
                result = api.handle( "GET", self.path )
                self.send_json(result)

            except ValueError as error:
                self.send_json( {"error": str(error)}, status=400 )

            except Exception as error:
                self.send_json( {"error": str(error)}, status=500 )

            return


        # 1. Map root URL to static/welcome.html
        if self.path == "/":
            self.path = "/application/static/welcome.html"

        elif self.path == "/welcome":
            self.path = "/application/static/welcome.html"

        elif self.path.startswith(("/css/", "/js/", "/assets/")):
            self.path = "/application/static" + self.path

        elif self.path == "/lab":
            self.path = "/application/static/lab.html"

        elif self.path.startswith("/static/"):
            self.path = "/application" + self.path

        else:
            self.path = "/application/static/404.html"

        return super().do_GET()

    def do_POST(self):

        if not self.path.startswith("/api/"):
            self.send_json( {"error": "POST endpoint not found"}, status=404 )
            return

        try:
            length = int(
                self.headers.get( "Content-Length", 0 ) )

            raw_body = self.rfile.read(length)

            body = ( json.loads(raw_body) if raw_body else {})

            result = api.handle( "POST", self.path, body )

            self.send_json( result, status=200 )

        except ValueError as error:
            self.send_json( {"error": str(error)}, status=400 )

        except Exception as error:
            self.send_json( {"error": str(error)}, status=500 )


    def do_DELETE(self):

        if not self.path.startswith("/api/"):
            self.send_json( {"error": "DELETE endpoint not found"}, status=404 )
            return

        try:
            length = int( self.headers.get( "Content-Length", 0 ) )

            raw_body = self.rfile.read(length)

            body = ( json.loads(raw_body) if raw_body else {} )

            result = api.handle( "DELETE", self.path, body )

            self.send_json( result, status=200 )

        except ValueError as error:
            self.send_json( {"error": str(error)}, status=400 )

        except Exception as error:
            self.send_json( {"error": str(error)}, status=500 )



    def send_json(self, data, status=200):

        response = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header( "Content-Type", "application/json" )
        self.send_header( "Content-Length", str(len(response)) )
        self.end_headers()

        self.wfile.write(response)


    
def main():

    server = HTTPServer( (HOST, PORT), CustomHandler )

    print(f"Cyber Hazard Lab running at http://{HOST}:{PORT}")

    try:
        server.serve_forever()


    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()