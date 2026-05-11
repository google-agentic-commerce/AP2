#!/usr/bin/env python3
"""HTTP server for simulating merchant-side events. Run on port 8081 (default).

Examples:
  curl -X POST
    "http://localhost:8081/trigger-price-drop?item_id=apple_0&price=5&stock=10"
"""

import json
import os
import time

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


_TEMP_DB = Path(os.environ.get("TEMP_DB_DIR", ".temp-db"))
_TRIGGER_STATE_PATH = os.environ.get(
    "MERCHANT_TRIGGER_STATE_PATH",
    str(_TEMP_DB / "merchant_trigger_state.json"),
)

PORT = int(os.environ.get("MERCHANT_TRIGGER_PORT", "8081"))


def _load_trigger_state_raw() -> dict[str, Any]:
  if not os.path.exists(_TRIGGER_STATE_PATH):
    return {}
  try:
    with open(_TRIGGER_STATE_PATH) as f:
      return json.load(f)
  except (json.JSONDecodeError, OSError):
    return {}


def _merge_trigger_state(
    item_id: str, value: float | dict[str, Any]
) -> dict[str, Any]:
  state = _load_trigger_state_raw()
  state[item_id] = value
  os.makedirs(os.path.dirname(_TRIGGER_STATE_PATH), exist_ok=True)
  with open(_TRIGGER_STATE_PATH, "w") as f:
    json.dump(state, f, indent=2)
  return state


class TriggerHandler(BaseHTTPRequestHandler):
  """Handles HTTP requests for simulating merchant-side events."""

  def log_message(self, format, *args):
    print(f"[trigger] {args[0]}")

  def _cors(self) -> None:
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type")

  def do_OPTIONS(self) -> None:
    self.send_response(204)
    self._cors()
    self.end_headers()

  def do_POST(self):
    parsed = urlparse(self.path)
    qs = parse_qs(parsed.query)
    item_id = (qs.get("item_id") or [None])[0]

    if not item_id:
      self.send_response(400)
      self.send_header("Content-Type", "application/json")
      self._cors()
      self.end_headers()
      self.wfile.write(json.dumps({"error": "item_id required"}).encode())
      return

    if parsed.path == "/trigger-price-drop":
      price_str = (qs.get("price") or ["5.0"])[0]
      price = float(price_str)
      stock_str = (qs.get("stock") or [None])[0]
      payload: dict[str, Any] = {"price": price, "_touch": time.time()}
      if stock_str is not None:
        payload["stock"] = max(0, int(stock_str))
      _merge_trigger_state(item_id, payload)
      stock_msg = f", stock {payload['stock']}" if "stock" in payload else ""
      self._json_ok({
          "ok": True,
          "item_id": item_id,
          "price": price,
          **({"stock": payload["stock"]} if "stock" in payload else {}),
          "message": (
              f"Price for {item_id} set to ${price}{stock_msg}. Shopping agent"
              " sees it on next check_product (web UI may nudge immediately"
              " via /state poll)."
          ),
      })
      return

    self.send_response(404)
    self._cors()
    self.end_headers()

  def _json_ok(self, body: dict[str, Any]) -> None:
    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self._cors()
    self.end_headers()
    self.wfile.write(json.dumps(body).encode())

  def do_GET(self):
    parsed = urlparse(self.path)
    qs = parse_qs(parsed.query)

    if parsed.path == "/state":
      item_id = (qs.get("item_id") or [None])[0]
      if not item_id:
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps({"error": "item_id required"}).encode())
        return
      state = _load_trigger_state_raw()
      entry = state.get(item_id)
      self.send_response(200)
      self.send_header("Content-Type", "application/json")
      self._cors()
      self.end_headers()
      self.wfile.write(
          json.dumps({"item_id": item_id, "entry": entry}).encode()
      )
      return

    if parsed.path in ("/", "/health"):
      self.send_response(200)
      self.send_header("Content-Type", "application/json")
      self._cors()
      self.end_headers()
      self.wfile.write(
          json.dumps({
              "status": "ok",
              "endpoints": [
                  (
                      "POST"
                      f" http://localhost:{PORT}/trigger-price-drop"
                      "?item_id=<item_id>&price=<price>[&stock=<stock>]"
                  ),
                  f"GET http://localhost:{PORT}/state?item_id=<item_id>",
              ],
          }).encode()
      )
    else:
      self.send_response(404)
      self._cors()
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
  print(f"Merchant trigger server: http://localhost:{PORT}/")
  print(f"State file: {_TRIGGER_STATE_PATH}")
  server.serve_forever()
