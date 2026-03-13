import http.server, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))
http.server.HTTPServer(("", 8001), http.server.SimpleHTTPRequestHandler).serve_forever()
