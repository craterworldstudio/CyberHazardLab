
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
from backend.state.manager import StateManager
from application.ntm.ntm import NetworkTopologyManager
from application.ncm.ncm import NetworkConfigurationManager
from application.api import API


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))


simulation = Simulation()

state_manager = StateManager(simulation)

ntm = NetworkTopologyManager(simulation)
ncm = NetworkConfigurationManager(simulation)

api = API(ntm, ncm, state_manager)

state_data = state_manager.load()
if state_data:
    sim_data = state_data.get("simulation", {})
    if sim_data.get("devices") or sim_data.get("subnets"):
        print("[CHL] Restoring simulation state from simulation_state.json...")
        api.handle("POST", "/api/simulation/import", body=state_data)
else:
    print("[CHL] No existing state found, starting fresh.")
    state_manager.reset()

class CustomHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):

        if self.path.startswith("/api/"):
            try:
                result = api.handle( "GET", self.path )
                if isinstance(result, tuple) and len(result) == 3 and isinstance(result[0], bytes):
                    content, ctype, fname = result
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
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
        

    def do_PUT(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = {}

        if content_length > 0:
            raw_body = self.rfile.read(content_length)
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, status=400)
                return

        try:
            result = api.handle("PUT", self.path, body)
            self.send_json(result, status=200)

        except ValueError as error:
            self.send_json({"error": str(error)}, status=400)

        except Exception as error:
            self.send_json({"error": str(error)}, status=500)

        


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