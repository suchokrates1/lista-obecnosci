"""KSeF 2.0 API client for token authentication and online invoice sessions."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, padding as sym_padding
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import requests

logger = logging.getLogger(__name__)

KSEF_ENVIRONMENTS = {
    "production": "https://api.ksef.mf.gov.pl/v2",
    "demo": "https://api-demo.ksef.mf.gov.pl/v2",
    "test": "https://api-test.ksef.mf.gov.pl/v2",
}

KSEF_ENVIRONMENT_TOKEN_KEYS = {
    "demo": "KSEF_TOKEN_DEMO",
    "test": "KSEF_TOKEN_TEST",
    "production": "KSEF_TOKEN_PRODUCTION",
}

FORM_CODE = {
    "systemCode": "FA (3)",
    "schemaVersion": "1-0E",
    "value": "FA",
}


class KSeFException(Exception):
    """Raised on KSeF API or protocol errors."""


@dataclass
class TokenInfo:
    token: str
    valid_until: datetime


@dataclass
class KSeFSendResult:
    session_reference_number: str
    invoice_reference_number: str
    session_status_code: Optional[int] = None
    session_status_description: Optional[str] = None
    invoice_status_code: Optional[int] = None
    invoice_status_description: Optional[str] = None
    ksef_number: Optional[str] = None
    upo_reference_number: Optional[str] = None
    upo_download_url: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.invoice_status_code == 200 or self.session_status_code == 200


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _sha256_base64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


def _encrypt_aes_cbc_pkcs7(data: bytes, key: bytes, iv: bytes) -> bytes:
    padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def resolve_ksef_token(environment: str) -> str:
    specific_key = KSEF_ENVIRONMENT_TOKEN_KEYS.get(environment)
    if specific_key:
        token = os.getenv(specific_key, "")
        if token:
            return token

    if environment == "test":
        demo_token = os.getenv("KSEF_TOKEN_DEMO", "")
        if demo_token:
            return demo_token

    return os.getenv("KSEF_TOKEN", "")


class KSeFClient:
    """Minimal KSeF 2.0 client supporting token auth and online invoice flow."""

    def __init__(
        self,
        environment: str = "demo",
        nip: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        if environment not in KSEF_ENVIRONMENTS:
            raise KSeFException(f"Invalid environment: {environment}")

        self.base_url = KSEF_ENVIRONMENTS[environment]
        self.environment = environment
        self.nip = nip or os.getenv("KSEF_NIP", "")
        self.ksef_token = token or resolve_ksef_token(environment)
        self.timeout = timeout
        self.http = requests.Session()

        self.authentication_reference_number: Optional[str] = None
        self.authentication_token: Optional[TokenInfo] = None
        self.access_token: Optional[TokenInfo] = None
        self.refresh_token: Optional[TokenInfo] = None

        if not self.nip:
            raise KSeFException("KSEF_NIP is required")
        if not self.ksef_token:
            raise KSeFException("KSEF_TOKEN is required")

    def _request(
        self,
        method: str,
        path: str,
        *,
        bearer_token: Optional[str] = None,
        json_data: Optional[Dict[str, Any]] = None,
        accept: str = "application/json",
        content_type: Optional[str] = "application/json",
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = {"Accept": accept}
        if content_type:
            headers["Content-Type"] = content_type
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        response = self.http.request(
            method,
            url,
            headers=headers,
            json=json_data,
            timeout=self.timeout,
        )
        if response.ok:
            return response

        raise KSeFException(self._format_error(response))

    def _format_error(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"KSeF request failed: HTTP {response.status_code}: {response.text}"

        if "exception" in payload:
            details = payload["exception"].get("exceptionDetailList") or []
            if details:
                first = details[0]
                joined = "; ".join(first.get("details") or [])
                if joined:
                    return (
                        f"KSeF request failed: HTTP {response.status_code}, "
                        f"{first.get('exceptionCode')}: {first.get('exceptionDescription')} ({joined})"
                    )
                return (
                    f"KSeF request failed: HTTP {response.status_code}, "
                    f"{first.get('exceptionCode')}: {first.get('exceptionDescription')}"
                )
        if "detail" in payload:
            return f"KSeF request failed: HTTP {response.status_code}: {payload.get('detail')}"
        return f"KSeF request failed: HTTP {response.status_code}: {payload}"

    def _is_token_valid(self, token_info: Optional[TokenInfo], skew_seconds: int = 30) -> bool:
        return bool(token_info and token_info.valid_until.timestamp() > time.time() + skew_seconds)

    def _build_context_identifier(self) -> Dict[str, str]:
        return {"type": "Nip", "value": self.nip}

    def fetch_public_key_certificate(self, usage: str) -> bytes:
        response = self._request("GET", "/security/public-key-certificates", content_type=None)
        certificates = response.json()
        candidates = [item for item in certificates if usage in (item.get("usage") or [])]
        if not candidates:
            raise KSeFException(f"No public key certificate found for usage {usage}")
        candidates.sort(key=lambda item: item["validTo"], reverse=True)
        return base64.b64decode(candidates[0]["certificate"])

    def _encrypt_with_public_key(self, payload: bytes, usage: str) -> str:
        cert_der = self.fetch_public_key_certificate(usage)
        certificate = x509.load_der_x509_certificate(cert_der)
        public_key = certificate.public_key()
        encrypted = public_key.encrypt(
            payload,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted).decode("ascii")

    def authenticate_by_token(self) -> None:
        challenge_response = self._request("POST", "/auth/challenge", json_data={})
        challenge_data = challenge_response.json()
        challenge = challenge_data["challenge"]
        timestamp_ms = challenge_data["timestampMs"]
        encrypted_token = self._encrypt_with_public_key(
            f"{self.ksef_token}|{timestamp_ms}".encode("utf-8"),
            "KsefTokenEncryption",
        )

        init_response = self._request(
            "POST",
            "/auth/ksef-token",
            json_data={
                "challenge": challenge,
                "contextIdentifier": self._build_context_identifier(),
                "encryptedToken": encrypted_token,
            },
        )
        payload = init_response.json()
        auth_token = payload["authenticationToken"]
        self.authentication_reference_number = payload["referenceNumber"]
        self.authentication_token = TokenInfo(
            token=auth_token["token"],
            valid_until=_parse_datetime(auth_token["validUntil"]),
        )
        logger.info("KSeF authentication initialized: %s", self.authentication_reference_number)

    def get_authentication_status(self) -> Dict[str, Any]:
        if not self.authentication_reference_number or not self.authentication_token:
            raise KSeFException("Authentication has not been initialized")
        response = self._request(
            "GET",
            f"/auth/{self.authentication_reference_number}",
            bearer_token=self.authentication_token.token,
        )
        return response.json()

    def redeem_authentication_tokens(self) -> None:
        if not self.authentication_token:
            raise KSeFException("Missing authentication operation token")
        response = self._request(
            "POST",
            "/auth/token/redeem",
            bearer_token=self.authentication_token.token,
            json_data={},
        )
        payload = response.json()
        self.access_token = TokenInfo(
            token=payload["accessToken"]["token"],
            valid_until=_parse_datetime(payload["accessToken"]["validUntil"]),
        )
        self.refresh_token = TokenInfo(
            token=payload["refreshToken"]["token"],
            valid_until=_parse_datetime(payload["refreshToken"]["validUntil"]),
        )

    def refresh_access_token(self) -> None:
        if not self.refresh_token:
            raise KSeFException("Missing refresh token")
        response = self._request(
            "POST",
            "/auth/token/refresh",
            bearer_token=self.refresh_token.token,
            json_data={},
        )
        payload = response.json()
        self.access_token = TokenInfo(
            token=payload["accessToken"]["token"],
            valid_until=_parse_datetime(payload["accessToken"]["validUntil"]),
        )

    def ensure_authenticated(self) -> None:
        if self._is_token_valid(self.access_token):
            return
        if self._is_token_valid(self.refresh_token):
            self.refresh_access_token()
            return
        self.authenticate_by_token()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            status = self.get_authentication_status()
            status_info = status.get("status") or {}
            code = status_info.get("code")
            if code == 200:
                self.redeem_authentication_tokens()
                return
            if code and code != 100:
                raise KSeFException(
                    f"KSeF authentication failed: {status_info.get('description')}"
                )
            time.sleep(1)
        raise KSeFException("KSeF authentication timed out")

    def _authorized_request(
        self,
        method: str,
        path: str,
        *,
        json_data: Optional[Dict[str, Any]] = None,
        accept: str = "application/json",
        content_type: Optional[str] = "application/json",
    ) -> requests.Response:
        self.ensure_authenticated()
        assert self.access_token is not None
        return self._request(
            method,
            path,
            bearer_token=self.access_token.token,
            json_data=json_data,
            accept=accept,
            content_type=content_type,
        )

    def create_encryption_info(self) -> Tuple[Dict[str, str], bytes, bytes]:
        symmetric_key = os.urandom(32)
        initialization_vector = os.urandom(16)
        encrypted_sym_key = self._encrypt_with_public_key(
            symmetric_key,
            "SymmetricKeyEncryption",
        )
        return (
            {
                "encryptedSymmetricKey": encrypted_sym_key,
                "initializationVector": base64.b64encode(initialization_vector).decode("ascii"),
            },
            symmetric_key,
            initialization_vector,
        )

    def open_online_session(self) -> Tuple[str, bytes, bytes]:
        encryption_info, symmetric_key, initialization_vector = self.create_encryption_info()
        response = self._authorized_request(
            "POST",
            "/sessions/online",
            json_data={
                "formCode": FORM_CODE,
                "encryption": encryption_info,
            },
        )
        payload = response.json()
        return payload["referenceNumber"], symmetric_key, initialization_vector

    def send_encrypted_invoice(
        self,
        session_reference_number: str,
        invoice_xml: str,
        symmetric_key: bytes,
        initialization_vector: bytes,
        offline_mode: bool = False,
    ) -> str:
        invoice_bytes = invoice_xml.encode("utf-8")
        encrypted_invoice = _encrypt_aes_cbc_pkcs7(invoice_bytes, symmetric_key, initialization_vector)
        response = self._authorized_request(
            "POST",
            f"/sessions/online/{session_reference_number}/invoices",
            json_data={
                "invoiceHash": _sha256_base64(invoice_bytes),
                "invoiceSize": len(invoice_bytes),
                "encryptedInvoiceHash": _sha256_base64(encrypted_invoice),
                "encryptedInvoiceSize": len(encrypted_invoice),
                "encryptedInvoiceContent": base64.b64encode(encrypted_invoice).decode("ascii"),
                "offlineMode": offline_mode,
            },
        )
        return response.json()["referenceNumber"]

    def close_online_session(self, session_reference_number: str) -> None:
        self._authorized_request(
            "POST",
            f"/sessions/online/{session_reference_number}/close",
            json_data={},
        )

    def get_session_status(self, session_reference_number: str) -> Dict[str, Any]:
        response = self._authorized_request("GET", f"/sessions/{session_reference_number}")
        return response.json()

    def get_session_invoice_status(
        self,
        session_reference_number: str,
        invoice_reference_number: str,
    ) -> Dict[str, Any]:
        response = self._authorized_request(
            "GET",
            f"/sessions/{session_reference_number}/invoices/{invoice_reference_number}",
        )
        return response.json()

    def get_session_invoices(self, session_reference_number: str) -> Dict[str, Any]:
        response = self._authorized_request("GET", f"/sessions/{session_reference_number}/invoices")
        return response.json()

    def download_invoice_xml(self, ksef_number: str) -> str:
        response = self._authorized_request(
            "GET",
            f"/invoices/ksef/{ksef_number}",
            accept="application/xml",
            content_type=None,
        )
        return response.text

    def download_invoice_upo(self, session_reference_number: str, ksef_number: str) -> str:
        response = self._authorized_request(
            "GET",
            f"/sessions/{session_reference_number}/invoices/ksef/{ksef_number}/upo",
            accept="application/xml",
            content_type=None,
        )
        return response.text

    def wait_for_invoice_processing(
        self,
        session_reference_number: str,
        invoice_reference_number: str,
        timeout_seconds: int = 120,
        poll_interval_seconds: float = 2.0,
    ) -> KSeFSendResult:
        deadline = time.monotonic() + timeout_seconds
        last_session_status: Optional[Dict[str, Any]] = None
        last_invoice_status: Optional[Dict[str, Any]] = None

        while time.monotonic() < deadline:
            last_session_status = self.get_session_status(session_reference_number)
            last_invoice_status = self.get_session_invoice_status(
                session_reference_number,
                invoice_reference_number,
            )
            invoice_status = (last_invoice_status.get("status") or {}).get("code")
            session_status = (last_session_status.get("status") or {}).get("code")
            if invoice_status in {200, 405, 410, 415, 430, 435, 440, 450, 500, 550}:
                return self._build_send_result(
                    session_reference_number,
                    invoice_reference_number,
                    last_session_status,
                    last_invoice_status,
                )
            if session_status in {200, 415, 440, 445, 500}:
                return self._build_send_result(
                    session_reference_number,
                    invoice_reference_number,
                    last_session_status,
                    last_invoice_status,
                )
            time.sleep(poll_interval_seconds)

        return self._build_send_result(
            session_reference_number,
            invoice_reference_number,
            last_session_status,
            last_invoice_status,
        )

    def _build_send_result(
        self,
        session_reference_number: str,
        invoice_reference_number: str,
        session_payload: Optional[Dict[str, Any]],
        invoice_payload: Optional[Dict[str, Any]],
    ) -> KSeFSendResult:
        session_status = (session_payload or {}).get("status") or {}
        invoice_status = (invoice_payload or {}).get("status") or {}
        upo_pages = ((session_payload or {}).get("upo") or {}).get("pages") or []
        return KSeFSendResult(
            session_reference_number=session_reference_number,
            invoice_reference_number=invoice_reference_number,
            session_status_code=session_status.get("code"),
            session_status_description=session_status.get("description"),
            invoice_status_code=invoice_status.get("code"),
            invoice_status_description=invoice_status.get("description"),
            ksef_number=(invoice_payload or {}).get("ksefNumber"),
            upo_reference_number=upo_pages[0].get("referenceNumber") if upo_pages else None,
            upo_download_url=(invoice_payload or {}).get("upoDownloadUrl"),
        )

    def send_invoice(
        self,
        invoice_xml: str,
        wait_for_completion: bool = True,
        timeout_seconds: int = 120,
        poll_interval_seconds: float = 2.0,
    ) -> KSeFSendResult:
        session_reference_number, symmetric_key, initialization_vector = self.open_online_session()
        invoice_reference_number = self.send_encrypted_invoice(
            session_reference_number,
            invoice_xml,
            symmetric_key,
            initialization_vector,
        )
        self.close_online_session(session_reference_number)

        if wait_for_completion:
            return self.wait_for_invoice_processing(
                session_reference_number,
                invoice_reference_number,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )

        return KSeFSendResult(
            session_reference_number=session_reference_number,
            invoice_reference_number=invoice_reference_number,
        )


def send_invoice_to_ksef(invoice_xml: str) -> Tuple[bool, Optional[KSeFSendResult], Optional[str]]:
    environment = os.getenv("KSEF_ENVIRONMENT", "demo")
    nip = os.getenv("KSEF_NIP", "")
    token = resolve_ksef_token(environment)

    if not nip:
        return False, None, "KSEF_NIP not configured"
    if not token:
        token_key = KSEF_ENVIRONMENT_TOKEN_KEYS.get(environment, "KSEF_TOKEN")
        return False, None, f"{token_key} not configured"

    try:
        client = KSeFClient(environment=environment, nip=nip, token=token)
        result = client.send_invoice(invoice_xml)
        if result.success:
            return True, result, None
        description = result.invoice_status_description or result.session_status_description or "Unknown KSeF status"
        return False, result, description
    except Exception as error:
        logger.exception("Unexpected error sending invoice to KSeF")
        return False, None, str(error)
