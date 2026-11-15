"""
Deterministic local HTTP mock server for Pey API.
Complies with OpenAPI 3.1.1 specification and Explorer 2 / Spec Miner 1 contracts.
"""

import http.server
import json
import socket
import threading
from typing import Any, Dict, List, Optional

# Minimal 1x1 valid transparent PNG (67 bytes) base64-encoded
DUMMY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class PeyMockHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard logging to keep test output clean
        pass

    @property
    def server_state(self) -> Dict[str, Any]:
        return self.server.state  # type: ignore[attr-defined]

    def do_GET(self):
        auth_header = self.headers.get("Authorization", "")
        path = self.path.split("?")[0].rstrip("/")
        self.server_state["captured_requests"].append({
            "method": "GET",
            "path": self.path,
            "headers": dict(self.headers),
        })

        # 1. Health check auth probe: /transaction/api-key
        if path == "/transaction/api-key":
            if self.server_state.get("unauthorized", False) or not auth_header.startswith("Bearer "):
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Unauthorized"}).encode("utf-8"))
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"items": [], "nextToken": None}).encode("utf-8"))
            return

        # 2. CoDi QR polling: /transaction/codi/qr/:id
        if path.startswith("/transaction/codi/qr/"):
            qr_id = path.split("/")[-1]
            if qr_id not in self.server_state["codi_qrs"]:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": {"message": "CoDi QR not found", "type": "NOT_FOUND"}}).encode("utf-8")
                )
                return

            qr_record = self.server_state["codi_qrs"][qr_id]
            status = qr_record.get("status", "PENDING")
            item: Dict[str, Any] = {
                "id": qr_id,
                "status": status,
                "amount": qr_record.get("amount", 0.0),
                "currency": "MXN",
            }
            if status == "PAID":
                item["datePaid"] = qr_record.get("datePaid", 1794718246)
                item["transactionId"] = f"tx_{qr_id}"

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"items": [item], "nextToken": None}).encode("utf-8"))
            return

        # 3. Payment link polling: /payment-link/:id
        if path.startswith("/payment-link/"):
            link_id = path.split("/")[-1]
            if link_id not in self.server_state["payment_links"]:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": {"message": "Payment link not found", "type": "NOT_FOUND"}}).encode("utf-8")
                )
                return

            link_record = self.server_state["payment_links"][link_id]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(link_record).encode("utf-8"))
            return

        # Fallback 404
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Not Found"}).encode("utf-8"))

    def do_POST(self):
        auth_header = self.headers.get("Authorization", "")
        path = self.path.split("?")[0].rstrip("/")
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        body: Dict[str, Any] = {}
        if body_bytes:
            try:
                body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                body = {}

        self.server_state["captured_requests"].append({
            "method": "POST",
            "path": self.path,
            "headers": dict(self.headers),
            "body": body,
        })

        if self.server_state.get("unauthorized", False) or not auth_header.startswith("Bearer "):
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Unauthorized"}).encode("utf-8"))
            return

        # 1. CoDi QR creation: /codi/qr
        if path == "/codi/qr":
            amount = body.get("amount")
            if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "error": {
                            "message": "Amount must be a number greater than or equal to 0",
                            "type": "INVALID_AMOUNT",
                        }
                    }).encode("utf-8")
                )
                return

            expiration = body.get("expiration", 0)
            if expiration != 0 and (not isinstance(expiration, int) or expiration < 360):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "error": {
                            "message": "Expiration must be 0 or at least 360 seconds",
                            "type": "INVALID_PARAMETER",
                        }
                    }).encode("utf-8")
                )
                return

            num_ref = str(body.get("numRef", "12345"))
            if not num_ref.isdigit() or len(num_ref) > 7:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "error": {
                            "message": "Numeric reference must be up to 7 digits",
                            "type": "INVALID_PARAMETER",
                        }
                    }).encode("utf-8")
                )
                return

            qr_count = len(self.server_state["codi_qrs"]) + 1
            qr_id = f"codi_{qr_count:04d}"
            qr_string = json.dumps({
                "TYP": 20,
                "v": {"DEV": "klipo_dev"},
                "ic": {"IDC": qr_id, "SER": 1000 + qr_count},
            })
            qr_image = DUMMY_PNG_BASE64 if body.get("generateImage", True) else None

            self.server_state["codi_qrs"][qr_id] = {
                "id": qr_id,
                "amount": float(amount),
                "concept": body.get("concept", ""),
                "status": "PENDING",
                "numRef": num_ref,
                "payload": body,
            }

            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({
                    "id": qr_id,
                    "qrString": qr_string,
                    "qrImage": qr_image,
                }).encode("utf-8")
            )
            return

        # 2. Payment Link creation: /payment-link/create
        if path == "/payment-link/create":
            amount = body.get("amount")
            if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "error": {
                            "message": "Amount must be greater than 0",
                            "type": "INVALID_AMOUNT",
                        }
                    }).encode("utf-8")
                )
                return

            success_url = str(body.get("successUrl", ""))
            back_url = str(body.get("backUrl", ""))
            if not success_url.startswith("https://") or not back_url.startswith("https://"):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "error": {
                            "message": "Success URL and back URL must use HTTPS",
                            "type": "INVALID_URL",
                        }
                    }).encode("utf-8")
                )
                return

            link_count = len(self.server_state["payment_links"]) + 1
            link_id = f"link_{link_count:04d}"
            checkout_url = f"https://app.mipey.mx/checkout/payment-link/{link_id}"

            self.server_state["payment_links"][link_id] = {
                "id": link_id,
                "amount": float(amount),
                "status": "pending",
                "url": checkout_url,
                "successUrl": success_url,
                "backUrl": back_url,
                "clientReferenceId": body.get("clientReferenceId"),
                "transactions": [],
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({
                    "id": link_id,
                    "url": checkout_url,
                }).encode("utf-8")
            )
            return

        # Fallback 404
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Not Found"}).encode("utf-8"))


class PeyMockServer:
    """Threaded local HTTP mock server simulating Pey Payment Gateway."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.server = http.server.HTTPServer((host, port), PeyMockHandler)
        self.port = self.server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.server.state = {  # type: ignore[attr-defined]
            "codi_qrs": {},
            "payment_links": {},
            "captured_requests": [],
            "unauthorized": False,
        }
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def reset(self):
        self.server.state["codi_qrs"] = {}  # type: ignore[attr-defined]
        self.server.state["payment_links"] = {}  # type: ignore[attr-defined]
        self.server.state["captured_requests"] = []  # type: ignore[attr-defined]
        self.server.state["unauthorized"] = False  # type: ignore[attr-defined]

    def mark_codi_paid(self, qr_id: str, date_paid: int = 1794718246):
        if qr_id in self.server.state["codi_qrs"]:  # type: ignore[attr-defined]
            self.server.state["codi_qrs"][qr_id]["status"] = "PAID"  # type: ignore[attr-defined]
            self.server.state["codi_qrs"][qr_id]["datePaid"] = date_paid  # type: ignore[attr-defined]

    def mark_link_paid(self, link_id: str, date_paid: int = 1794718246):
        if link_id in self.server.state["payment_links"]:  # type: ignore[attr-defined]
            record = self.server.state["payment_links"][link_id]  # type: ignore[attr-defined]
            record["status"] = "paid"
            record["transactions"] = [{
                "transactionId": f"tx_{link_id}",
                "paymentMethod": "CODI",
                "datePaid": date_paid,
                "amount": record.get("amount", 0.0),
            }]

    def set_unauthorized(self, state: bool = True):
        self.server.state["unauthorized"] = state  # type: ignore[attr-defined]

    def get_captured_requests(self) -> List[Dict[str, Any]]:
        return list(self.server.state["captured_requests"])  # type: ignore[attr-defined]
