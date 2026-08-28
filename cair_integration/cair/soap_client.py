"""CAIR2 SOAP client for submitting HL7 VXU messages."""

from __future__ import annotations

import logging
from typing import Optional

import requests

from cair_integration.cair.ack_parser import parse_ack
from cair_integration.models import CairSendResult

logger = logging.getLogger(__name__)


class CairSoapClient:
    """Submits HL7 messages to CAIR2 via SOAP.

    Replace envelope/body with the exact WSDL contract CAIR provides
    during onboarding. This class uses a generic placeholder envelope.
    """

    def __init__(self, soap_url: str, username: str = "", password: str = ""):
        self._soap_url = soap_url
        self._username = username
        self._password = password

    def send_vxu(self, hl7_message: str) -> CairSendResult:
        if not self._soap_url:
            return self._mock_send(hl7_message)

        envelope = self._build_envelope(hl7_message)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "submitSingleMessage",
        }

        try:
            response = requests.post(
                self._soap_url,
                data=envelope.encode("utf-8"),
                headers=headers,
                auth=(self._username, self._password) if self._username else None,
                timeout=60,
            )
            response.raise_for_status()
            ack_hl7 = self._extract_hl7_from_soap(response.text)
            ack = parse_ack(ack_hl7)

            return CairSendResult(
                success=ack.success,
                temporary_error=ack.temporary_error,
                ack_code=ack.ack_code,
                error_details="; ".join(ack.errors),
                raw_response=ack.raw,
            )
        except requests.Timeout:
            return CairSendResult(
                success=False,
                temporary_error=True,
                error_details="CAIR SOAP request timed out",
            )
        except requests.RequestException as exc:
            return CairSendResult(
                success=False,
                temporary_error=True,
                error_details=str(exc),
            )

    def _build_envelope(self, hl7_message: str) -> str:
        escaped = (
            hl7_message.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <submitSingleMessage xmlns="http://cair.cdph.ca.gov/">
      <hl7Message>{escaped}</hl7Message>
    </submitSingleMessage>
  </soap:Body>
</soap:Envelope>"""

    @staticmethod
    def _extract_hl7_from_soap(soap_response: str) -> str:
        start = soap_response.find("MSH|")
        if start == -1:
            return soap_response
        end = soap_response.find("</", start)
        if end == -1:
            return soap_response[start:]
        return soap_response[start:end]

    def _mock_send(self, hl7_message: str) -> CairSendResult:
        """Local/dev fallback when CAIR endpoint is not configured."""
        logger.warning("CAIR_SOAP_URL not set; using mock ACK response")
        control_id = ""
        for line in hl7_message.replace("\r", "\n").split("\n"):
            if line.startswith("MSH|"):
                fields = line.split("|")
                if len(fields) > 9:
                    control_id = fields[9]
                break

        mock_ack = (
            f"MSH|^~\\&|CAIR2|CAIRLO|MyEMR|SF-012218|"
            f"20260101120000||ACK^V04^ACK|{control_id}|P|2.5.1\r"
            f"MSA|AA|{control_id}\r"
        )
        ack = parse_ack(mock_ack)
        return CairSendResult(
            success=True,
            temporary_error=False,
            ack_code=ack.ack_code,
            raw_response=mock_ack,
        )
