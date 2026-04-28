#!/usr/bin/env python3
"""Custom ADK server with request logging for the auto-poll path.

Logs incoming A2A message/stream requests to LOGS_DIR/shopping-agent.log.
"""

import json
import logging
import os

from pathlib import Path

import uvicorn

from google.adk.cli.fast_api import get_fast_api_app
from starlette.middleware.base import (
  BaseHTTPMiddleware,
  RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response


_logger = logging.getLogger("shopping_agent")
_seen_sessions = set()


class A2ARequestLoggingMiddleware(BaseHTTPMiddleware):
  """Logs incoming A2A message/stream requests.

  This includes auto-poll check_product_now requests.
  """

  async def dispatch(
      self, request: Request, call_next: RequestResponseEndpoint
  ) -> Response:
    if request.method == "POST":
      try:
        body = await request.body()
        if body:
          data = json.loads(body)
          method = data.get("method", "")
          params = data.get("params") or {}
          metadata = params.get("metadata") or {}
          if method == "message/stream":
            msg = params.get("message") or {}
            parts = msg.get("parts") or []
            session_id_full = metadata.get("sessionId", "?")
            session_id = session_id_full[:8]

            if session_id_full != "?" and session_id_full not in _seen_sessions:
              _seen_sessions.add(session_id_full)
              try:
                for handler in _logger.handlers:
                  if (
                      isinstance(handler, logging.FileHandler)
                      and handler.stream
                  ):
                    handler.stream.seek(0)
                    handler.stream.truncate()
                _logger.info(
                    "Cleared log file for new session: %s...", session_id
                )
              except OSError as e:
                _logger.error("Failed to clear log: %s", e)

            for p in parts:
              if p.get("kind") == "text":
                text = (p.get("text") or "")[:120]
                _logger.info(
                    "A2A message/stream received session=%s... text=%r",
                    session_id,
                    text,
                )
              elif p.get("kind") == "data":
                d = p.get("data") or {}
                msg_type = d.get("type", "?")
                if msg_type == "check_product_now":
                  src = d.get("source", "?")
                  _logger.info(
                      "A2A check_product_now "
                      "(source=%s) session=%s... "
                      "item_id=%s price_cap=%s",
                      src,
                      session_id,
                      d.get("item_id", "?"),
                      d.get("price_cap", "?"),
                  )
                else:
                  _logger.info(
                      "A2A message/stream received session=%s... data type=%s",
                      session_id,
                      msg_type,
                  )
      except (json.JSONDecodeError, KeyError) as e:
        _logger.debug("A2A request log skip: %s", e)
    return await call_next(request)


if __name__ == "__main__":
  logs_dir = os.environ.get("LOGS_DIR", ".logs")
  os.makedirs(logs_dir, exist_ok=True)
  log_file = os.path.join(logs_dir, "shopping-agent.log")

  file_handler = logging.FileHandler(log_file, mode="a")
  file_handler.setFormatter(
      logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
  )
  _logger.addHandler(file_handler)
  _logger.setLevel(logging.INFO)

  app = get_fast_api_app(
      agents_dir=".",
      web=False,
      a2a=True,
      port=8080,
      # temporarily allow all origins
      allow_origins=["*"],
  )
  app.add_middleware(A2ARequestLoggingMiddleware)

  @app.get("/a2a/shopping_agent/mandates/{mandate_id}")
  async def get_mandate(mandate_id: str):
    temp_db_dir = os.environ.get("TEMP_DB_DIR", ".temp-db")
    temp_db = Path(temp_db_dir)
    file_path = temp_db / f"{mandate_id}.sdjwt"

    if not file_path.exists():
      return Response(
          content="Mandate not found", status_code=404, media_type="text/plain"
      )

    return Response(
        content=file_path.read_text(encoding="ascii"), media_type="text/plain"
    )

  uvicorn.run(app, host="127.0.0.1", port=8080)
