"""CAIR2 SOAP client for submitting HL7 VXU messages."""

from __future__ import annotations

import logging
import html
import xml.sax.saxutils
from typing import Optional

import requests

from cair_integration.cair.ack_parser import parse_ack
from cair_integration.models import CairSendResult

logger = logging.getLogger(__name__)

CAIR_SOAP_NAMESPACE = "urn:cdc:iisb:2011"
CAIR_SOAP_ACTION = "urn:cdc:iisb:2011:submitSingleMessage"


class CairSoapClient:
    """Submits HL7 messages to CAIR2 via SOAP 1.2 submitSingleMessage."""

    def __init__(
        self,
        soap_url: str,
        username: str = "",
        password: str = "",
        facility_id: str = "",
    ):
        self._soap_url = soap_url
        self._username = username
        self._password = password
        self._facility_id = facility_id

    def send_vxu(self, hl7_message: str) -> CairSendResult:
        if not self._soap_url:
            return self._mock_send(hl7_message)

        if not self._username or not self._password:
            return CairSendResult(
                success=False,
                temporary_error=False,
                error_details=(
                    "CAIR_SOAP_USERNAME and CAIR_SOAP_PASSWORD must be set in .env "
                    "(contact CAIRDataExchange@cdph.ca.gov for onboarding credentials)"
                ),
            )

        envelope = self._build_envelope(hl7_message)
        headers = {
            "Content-Type": (
                f'application/soap+xml; charset=utf-8; action="{CAIR_SOAP_ACTION}"'
            ),
        }

        try:
            response = requests.post(
                self._soap_url,
                data=envelope.encode("utf-8"),
                headers=headers,
                timeout=60,
            )
            if not response.ok:
                detail = self._format_http_error(response)
                logger.warning("CAIR SOAP HTTP %s: %s", response.status_code, detail[:500])
                return CairSendResult(
                    success=False,
                    temporary_error=True,
                    error_details=detail,
                    raw_response=response.text,
                )

            ack_hl7 = self._extract_hl7_from_soap(response.text)
            ack = parse_ack(ack_hl7)

            return CairSendResult(
                success=ack.success,
                temporary_error=ack.temporary_error,
                ack_code=ack.ack_code,
                error_details="; ".join(ack.errors),
                raw_response=ack.raw or response.text,
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
        username = xml.sax.saxutils.escape(self._username)
        password = xml.sax.saxutils.escape(self._password)
        facility_id = xml.sax.saxutils.escape(self._facility_id)
        hl7_xml = xml.sax.saxutils.escape(hl7_message)

        return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <submitSingleMessage xmlns="{CAIR_SOAP_NAMESPACE}">
      <username>{username}</username>
      <password>{password}</password>
      <facilityID>{facility_id}</facilityID>
      <hl7Message>{hl7_xml}</hl7Message>
    </submitSingleMessage>
  </soap:Body>
</soap:Envelope>"""

    @staticmethod
    def _format_http_error(response: requests.Response) -> str:
        body = (response.text or "").strip()
        if body:
            return f"{response.status_code} {response.reason}: {body[:1000]}"
        return f"{response.status_code} {response.reason} for url: {response.url}"

    @staticmethod
    def _extract_hl7_from_soap(soap_response: str) -> str:
        for tag in ("<return>", "<hl7Message>"):
            start = soap_response.find(tag)
            if start == -1:
                continue
            content_start = start + len(tag)
            end_tag = tag.replace("<", "</")
            end = soap_response.find(end_tag, content_start)
            if end == -1:
                continue
            payload = soap_response[content_start:end].strip()
            payload = html.unescape(payload)
            if "MSH|" in payload:
                msh_start = payload.find("MSH|")
                return payload[msh_start:]

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
            f"MSH|^~\\&|CAIR2|CAIR2|ClaudMD|SF-013259|"
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
