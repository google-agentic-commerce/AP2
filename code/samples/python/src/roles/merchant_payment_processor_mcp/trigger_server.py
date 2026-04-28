#!/usr/bin/env python3
"""HTTP server for initiating payment processing.

Run separately on port 8083.
"""

import asyncio
import json
import os

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import server as mcp_server


PORT = int(os.environ.get("MERCHANT_PAYMENT_PROCESSOR_TRIGGER_PORT", "8083"))


class TriggerHandler(BaseHTTPRequestHandler):
  """Handles HTTP requests for initiating payment processing."""

  def log_message(self, format, *args):
    print(f"[trigger] {args[0]}")

  def do_POST(self):
    parsed = urlparse(self.path)
    if parsed.path == "/initiate-payment":
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

      # Check that all required fields are present.
      for field in [
          "payment_token",
          "checkout_jwt_hash",
          "open_checkout_hash",
      ]:
        if not data.get(field):
          self.send_response(400)
          self.send_header("Content-Type", "application/json")
          self.end_headers()
          self.wfile.write(json.dumps({"error": f"{field} required"}).encode())
          return

      result = asyncio.run(
          mcp_server.initiate_payment(
              payment_token,
              checkout_jwt_hash,
              open_checkout_hash,
          )
      )
      self.send_response(200)
      self.send_header("Content-Type", "application/json")
      self.end_headers()
      self.wfile.write(json.dumps(result, default=str).encode())
    else:
      self.send_response(404)
      self.end_headers()


class ReuseHTTPServer(HTTPServer):
  allow_reuse_address = True


if __name__ == "__main__":
  try:
    httpd = ReuseHTTPServer(("127.0.0.1", PORT), TriggerHandler)
  except OSError as e:
    if e.errno == 48:
      print(
          f"Error: Port {PORT} is already in use. "
          f"Kill the process with: lsof -ti:{PORT} | xargs kill -9"
      )
    raise
  print(
      "Merchant payment processor trigger server:"
      f" http://localhost:{PORT}/initiate-payment"
  )
  httpd.serve_forever()
