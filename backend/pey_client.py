"""
Pey API Async Client (backend/pey_client.py)
Provides authenticated non-blocking communication with Pey Mexico API.
Supports:
- Credential verification (GET /transaction/api-key)
- CoDi QR creation with Banxico payload and base64 PNG (POST /codi/qr)
- Payment Link generation (POST /payment-link/create)
- CoDi QR transaction polling (GET /transaction/codi/qr/{id})
- Payment Link status polling (GET /payment-link/{id})
"""

import os
import re
import uuid
from typing import Any, Dict, List, Optional, Union

import httpx

def get_pey_base_url() -> str:
    return (
        os.getenv("PEY_BASE_URL")
        or os.getenv("PEY_API_BASE_URL")
        or "https://api.pey.mx"
    ).rstrip("/")


PEY_BASE_URL = get_pey_base_url()
DEFAULT_SUCCESS_URL = os.getenv("PEY_SUCCESS_URL", "https://klipo.onrender.com/success")
DEFAULT_BACK_URL = os.getenv("PEY_BACK_URL", "https://klipo.onrender.com/cancel")


class PeyError(Exception):
    """Base exception for all Pey client errors."""
    pass


class PeyAuthError(PeyError):
    """Raised when authentication fails (401 Unauthorized or missing key)."""
    pass


class PeyConnectionError(PeyError):
    """Raised on network, timeout, or DNS failure."""
    pass


class PeyAPIError(PeyError):
    """Raised when Pey returns an unexpected HTTP error code."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def get_pey_api_key() -> str:
    """
    Retrieves the Pey API Key from:
    1. Environment variable PEY_API_KEY
    2. Fallback file apiPey.txt (DO NOT commit to git)
    """
    key = os.getenv("PEY_API_KEY", "").strip()
    if key:
        return key

    candidates = [
        os.path.join(os.getcwd(), "apiPey.txt"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apiPey.txt"),
        "/home/jesusfloreslap/prog/klipo/apiPey.txt",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return content
            except Exception:
                pass

    return ""


class PeyClient:
    """Async client for interacting with the Pey Mexico API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self._explicit_key = api_key
        self._explicit_base_url = base_url
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        if self._explicit_base_url is not None:
            return self._explicit_base_url.rstrip("/")
        return get_pey_base_url()

    @base_url.setter
    def base_url(self, value: Optional[str]):
        self._explicit_base_url = value

    @property
    def api_key(self) -> str:
        if self._explicit_key is not None:
            return self._explicit_key
        return get_pey_api_key()

    def _get_headers(self) -> Dict[str, str]:
        key = self.api_key
        if not key:
            raise PeyAuthError("PEY_API_KEY is not configured or apiPey.txt is missing.")
        # Pey strictly enforces Authorization: Bearer <key> (Header x-api-key is rejected with 401)
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def check_credentials(self) -> Dict[str, Any]:
        """
        Verifies API key credentials against GET https://api.pey.mx/transaction/api-key.
        Returns the JSON response dict on HTTP 200.
        Raises PeyAuthError on 401, PeyConnectionError on network error, PeyAPIError on others.
        """
        url = f"{self.base_url}/transaction/api-key"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                raise PeyConnectionError(f"Failed to connect to Pey API ({url}): {exc}") from exc

        if resp.status_code == 200:
            try:
                data = resp.json() if resp.text else {}
            except Exception as exc:
                raise PeyAPIError(
                    f"Malformed JSON response from Pey API: {exc}",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )
            return {"authenticated": True, "status": "ok", **data}
        elif resp.status_code == 401:
            raise PeyAuthError(f"Pey credentials rejected (401 Unauthorized): {resp.text}")
        else:
            raise PeyAPIError(
                f"Pey credential check returned HTTP {resp.status_code}: {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

    async def create_codi_qr(
        self,
        amount: float,
        concept: str = "Cobro Klipo",
        num_ref: Optional[Union[str, int]] = None,
        expiration: int = 0,
        generate_image: bool = True,
        bank_account_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calls POST https://api.pey.mx/codi/qr.
        - amount: float >= 0 (supports decimal amounts down to $0.01 / $0.05 MXN).
        - num_ref: 1-7 digits numeric string.
        - expiration: 0 (no expiration) or >= 360 seconds.
        - generate_image: True to receive base64 PNG in qrImage.
        Returns dict with: 'id' (IDC string), 'qrString' (Banxico payload), 'qrImage' (base64 PNG).
        """
        if amount < 0:
            raise ValueError("Amount must be greater than or equal to 0.")

        # Ensure numRef is numeric and 1-7 digits
        if num_ref is not None:
            clean_ref = re.sub(r"\D", "", str(num_ref))
            if not clean_ref:
                clean_ref = str(uuid.uuid4().int % 9000000 + 1000000)
            elif len(clean_ref) > 7:
                clean_ref = clean_ref[-7:]
        else:
            clean_ref = str(uuid.uuid4().int % 9000000 + 1000000)

        # Expiration constraint: 0 or >= 360
        if expiration < 0:
            expiration = 0
        elif 0 < expiration < 360:
            expiration = 360

        payload: Dict[str, Any] = {
            "amount": float(amount),
            "concept": (concept or "Cobro Klipo")[:40],
            "numRef": clean_ref,
            "expiration": int(expiration),
            "generateImage": bool(generate_image),
        }
        if bank_account_id:
            payload["bankAccountId"] = bank_account_id
        if metadata:
            payload["metadata"] = metadata

        url = f"{self.base_url}/codi/qr"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise PeyConnectionError(f"Failed to connect to Pey API ({url}): {exc}") from exc

        if resp.status_code in (200, 201):
            try:
                return resp.json()
            except Exception as exc:
                raise PeyAPIError(
                    f"Malformed JSON response from Pey API: {exc}",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )
        elif resp.status_code == 401:
            raise PeyAuthError(f"Pey authentication failed (401): {resp.text}")
        else:
            raise PeyAPIError(
                f"Pey create_codi_qr failed (HTTP {resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

    async def create_payment_link(
        self,
        amount: float,
        success_url: Optional[str] = None,
        back_url: Optional[str] = None,
        client_reference_id: Optional[str] = None,
        has_tip: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calls POST https://api.pey.mx/payment-link/create.
        - amount: float > 0.
        - success_url / back_url: must use HTTPS.
        Returns dict with: 'id' (ULID string), 'url' (hosted checkout URL).
        """
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")

        s_url = success_url or DEFAULT_SUCCESS_URL
        b_url = back_url or DEFAULT_BACK_URL

        # Ensure HTTPS for URLs as required by Pey specification
        if not s_url.startswith("https://"):
            s_url = "https://" + s_url.split("://", 1)[-1]
        if not b_url.startswith("https://"):
            b_url = "https://" + b_url.split("://", 1)[-1]

        payload: Dict[str, Any] = {
            "amount": float(amount),
            "successUrl": s_url,
            "backUrl": b_url,
            "hasTip": bool(has_tip),
        }
        if client_reference_id:
            payload["clientReferenceId"] = str(client_reference_id)[:255]
        if metadata:
            payload["metadata"] = metadata

        url = f"{self.base_url}/payment-link/create"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise PeyConnectionError(f"Failed to connect to Pey API ({url}): {exc}") from exc

        if resp.status_code in (200, 201):
            try:
                return resp.json()
            except Exception as exc:
                raise PeyAPIError(
                    f"Malformed JSON response from Pey API: {exc}",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )
        elif resp.status_code == 401:
            raise PeyAuthError(f"Pey authentication failed (401): {resp.text}")
        else:
            raise PeyAPIError(
                f"Pey create_payment_link failed (HTTP {resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

    async def get_codi_qr_transactions(self, codi_qr_id: str) -> Dict[str, Any]:
        """
        Calls GET https://api.pey.mx/transaction/codi/qr/{codi_qr_id}.
        Returns dict with: 'items' (list of transactions), 'nextToken'.
        """
        url = f"{self.base_url}/transaction/codi/qr/{codi_qr_id}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                raise PeyConnectionError(f"Failed to connect to Pey API ({url}): {exc}") from exc

        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception as exc:
                raise PeyAPIError(
                    f"Malformed JSON response from Pey API: {exc}",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )
        elif resp.status_code == 404:
            return {"items": [], "nextToken": None}
        elif resp.status_code == 401:
            raise PeyAuthError(f"Pey authentication failed (401): {resp.text}")
        else:
            raise PeyAPIError(
                f"Pey get_codi_qr_transactions failed (HTTP {resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

    async def is_codi_qr_paid(self, codi_qr_id: str) -> bool:
        """Checks if any item in the CoDi QR transaction list has status == 'PAID'."""
        data = await self.get_codi_qr_transactions(codi_qr_id)
        items = data.get("items", [])
        return any(str(item.get("status", "")).upper() == "PAID" for item in items)

    async def get_payment_link_status(self, payment_link_id: str) -> Dict[str, Any]:
        """
        Calls GET https://api.pey.mx/payment-link/{payment_link_id}.
        Returns dict with link status ('pending', 'processing', 'paid', 'partial').
        """
        url = f"{self.base_url}/payment-link/{payment_link_id}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                raise PeyConnectionError(f"Failed to connect to Pey API ({url}): {exc}") from exc

        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception as exc:
                raise PeyAPIError(
                    f"Malformed JSON response from Pey API: {exc}",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )
        elif resp.status_code == 404:
            return {"id": payment_link_id, "status": "not_found", "transactions": []}
        elif resp.status_code == 401:
            raise PeyAuthError(f"Pey authentication failed (401): {resp.text}")
        else:
            raise PeyAPIError(
                f"Pey get_payment_link_status failed (HTTP {resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

    async def is_payment_link_paid(self, payment_link_id: str) -> bool:
        """Checks if the payment link status is 'paid'."""
        data = await self.get_payment_link_status(payment_link_id)
        status_val = str(data.get("status", "")).lower()
        return status_val == "paid"


# Module-level convenience functions using default client instance
_default_client: Optional[PeyClient] = None


def get_pey_client() -> PeyClient:
    global _default_client
    if _default_client is None:
        _default_client = PeyClient()
    return _default_client


async def check_credentials() -> Dict[str, Any]:
    return await get_pey_client().check_credentials()


async def create_codi_qr(
    amount: float,
    concept: str = "Cobro Klipo",
    num_ref: Optional[Union[str, int]] = None,
    expiration: int = 0,
    generate_image: bool = True,
    bank_account_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return await get_pey_client().create_codi_qr(
        amount=amount,
        concept=concept,
        num_ref=num_ref,
        expiration=expiration,
        generate_image=generate_image,
        bank_account_id=bank_account_id,
        metadata=metadata,
    )


async def create_payment_link(
    amount: float,
    success_url: Optional[str] = None,
    back_url: Optional[str] = None,
    client_reference_id: Optional[str] = None,
    has_tip: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return await get_pey_client().create_payment_link(
        amount=amount,
        success_url=success_url,
        back_url=back_url,
        client_reference_id=client_reference_id,
        has_tip=has_tip,
        metadata=metadata,
    )


async def get_codi_qr_transactions(codi_qr_id: str) -> Dict[str, Any]:
    return await get_pey_client().get_codi_qr_transactions(codi_qr_id)


async def is_codi_qr_paid(codi_qr_id: str) -> bool:
    return await get_pey_client().is_codi_qr_paid(codi_qr_id)


async def get_payment_link_status(payment_link_id: str) -> Dict[str, Any]:
    return await get_pey_client().get_payment_link_status(payment_link_id)


async def is_payment_link_paid(payment_link_id: str) -> bool:
    return await get_pey_client().is_payment_link_paid(payment_link_id)
