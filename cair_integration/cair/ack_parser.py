"""Parse CAIR2 HL7 ACK responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class AckResult:
    ack_code: str
    message_control_id: str
    errors: List[str]
    raw: str

    @property
    def success(self) -> bool:
        return self.ack_code == "AA"

    @property
    def temporary_error(self) -> bool:
        return self.ack_code == "AE"

    @property
    def permanent_error(self) -> bool:
        return self.ack_code == "AR"


def _split_segments(message: str) -> List[str]:
    normalized = message.replace("\r\n", "\r").replace("\n", "\r")
    return [seg for seg in normalized.split("\r") if seg.strip()]


def _split_fields(segment: str) -> List[str]:
    return segment.split("|")


def parse_ack(hl7_ack: str) -> AckResult:
    segments = _split_segments(hl7_ack)
    ack_code = ""
    message_control_id = ""
    errors: List[str] = []

    for segment in segments:
        fields = _split_fields(segment)
        seg_type = fields[0]

        if seg_type == "MSA" and len(fields) > 2:
            ack_code = fields[1]
            message_control_id = fields[2]
        elif seg_type == "ERR":
            error_text = "|".join(fields[1:]) if len(fields) > 1 else "Unknown error"
            errors.append(error_text)

    return AckResult(
        ack_code=ack_code,
        message_control_id=message_control_id,
        errors=errors,
        raw=hl7_ack,
    )
