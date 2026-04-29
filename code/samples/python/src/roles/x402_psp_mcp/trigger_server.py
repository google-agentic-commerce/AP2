#!/usr/bin/env python3
"""HTTP server for receiving payment settlement requests.

Run separately on port 8084.
"""

import json
import os

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import server as mcp_server


PORT = int(os.environ.get("X402_PSP_TRIGGER_PORT", "8084"))


class TriggerHandler(BaseHTTPRequestHandler):
  """Handles HTTP requests for payment settlement."""

  def log_message(self, format, *args):
    print(f"[trigger] {args[0]}")

  def do_POST(self):
    parsed = urlparse(self.path)
    if parsed.path == "/settle-payment":
      payment_token = None
      try:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body) if body else {}
        payment_token = data.get("payment_token")
        checkout_jwt_hash = data.get("checkout_jwt_hash")
        open_checkout_hash = data.get("open_checkout_hash")
      except json.JSONDecodeError:
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "invalid JSON"}).encode())
        return

      if not payment_token:
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"error": "payment_token required"}).encode()
        )
        return

      print(f"[trigger] Received payment token: {payment_token[:20]}...")

      result = mcp_server.settle_payment(
          payment_token, checkout_jwt_hash, open_checkout_hash
      )

      self.send_response(200)
      self.send_header("Content-Type", "application/json")
      self.end_headers()
      self.wfile.write(json.dumps(result).encode())
    else:
      self.send_response(404)
      self.end_headers()


class ReuseHTTPServer(HTTPServer):
  allow_reuse_address = True


if __name__ == "__main__":
  try:
    server = ReuseHTTPServer(("127.0.0.1", PORT), TriggerHandler)
  except OSError as e:
    if e.errno == 48:
      print(
          f"Error: Port {PORT} is already in use. "
          f"Kill the process with: lsof -ti:{PORT} | xargs kill -9"
      )
    raise
  print(f"x402 PSP trigger server: http://localhost:{PORT}/settle-payment")
  server.serve_forever()
