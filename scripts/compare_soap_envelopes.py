"""Compare old vs new SOAP envelope responses."""
import time
import xml.sax.saxutils

import requests

URL = "https://cdph-interop-stage.cdph.ca.gov/services/client_Service.client_ServiceHttpSoap12Endpoint"
HL7 = "MSH|test\r"

OLD = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <submitSingleMessage xmlns="http://cair.cdph.ca.gov/">
      <hl7Message>{HL7}</hl7Message>
    </submitSingleMessage>
  </soap:Body>
</soap:Envelope>"""

NEW = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <submitSingleMessage xmlns="urn:cdc:iisb:2011">
      <username>testuser</username>
      <password>testpass</password>
      <facilityID>SF-013259</facilityID>
      <hl7Message>{xml.sax.saxutils.escape(HL7)}</hl7Message>
    </submitSingleMessage>
  </soap:Body>
</soap:Envelope>"""

cases = [
    ("old", OLD, {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "submitSingleMessage"}),
    (
        "new",
        NEW,
        {
            "Content-Type": (
                'application/soap+xml; charset=utf-8; action="urn:cdc:iisb:2011:submitSingleMessage"'
            )
        },
    ),
    (
        "connectivity",
        """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <connectivityTest xmlns="urn:cdc:iisb:2011">
      <username></username>
      <password></password>
      <facilityID>SF-013259</facilityID>
    </connectivityTest>
  </soap:Body>
</soap:Envelope>""",
        {
            "Content-Type": (
                'application/soap+xml; charset=utf-8; action="urn:cdc:iisb:2011:connectivityTest"'
            )
        },
    ),
]

for name, body, headers in cases:
    start = time.time()
    try:
        r = requests.post(URL, data=body.encode("utf-8"), headers=headers, timeout=90)
        elapsed = time.time() - start
        print(f"=== {name} === {elapsed:.2f}s status={r.status_code}")
        print(r.text[:500])
    except Exception as exc:
        elapsed = time.time() - start
        print(f"=== {name} === {elapsed:.2f}s error={type(exc).__name__}: {exc}")
