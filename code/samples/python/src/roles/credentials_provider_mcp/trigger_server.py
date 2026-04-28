#!/usr/bin/env python3
"""HTTP server for receiving payment receipts. Run separately on port 8082."""

import json
import os

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import server as mcp_server


PORT = int(os.environ.get("CREDENTIALS_PROVIDER_TRIGGER_PORT", "8082"))


class TriggerHandler(BaseHTTPRequestHandler):
  """Handles HTTP requests for receiving payment receipts."""

  def log_message(self, format, *args):
    print(f"[trigger] {args[0]}")

  def do_POST(self):
    parsed = urlparse(self.path)
    if parsed.path == "/payment-receipt":
      payment_receipt = None
      try:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body) if body else {}
        payment_receipt = data.get("payment_receipt")
      except json.JSONDecodeError:
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "invalid JSON"}).encode())
        return

      if not payment_receipt:
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"error": "payment_receipt required"}).encode()
        )
        return

      print(f"[trigger] Received payment receipt: {payment_receipt[:20]}...")

      mcp_server.verify_payment_receipt(payment_receipt)

      self.send_response(200)
      self.send_header("Content-Type", "application/json")
      self.end_headers()
      self.wfile.write(json.dumps({"status": "ok"}).encode())
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
  print(
      "Credentials provider trigger server:"
      f" http://localhost:{PORT}/payment-receipt"
  )
  server.serve_forever()
