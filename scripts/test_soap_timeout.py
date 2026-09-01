"""Test SOAP 1.2 submitSingleMessage with longer timeout."""
import time
import xml.sax.saxutils

import requests

URL = "https://cdph-interop-stage.cdph.ca.gov/services/client_Service.client_ServiceHttpSoap12Endpoint"
HL7 = (
    "MSH|^~\\&|ClaudMD|SF-013259||CAIR2|20260101120000||VXU^V04^VXU_V04|"
    "timeout-test|P|2.5.1|||AL|AL|||||Z22^CDCPHINVS|SF-013259\r"
)
body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <submitSingleMessage xmlns="urn:cdc:iisb:2011">
      <username>test</username>
      <password>test</password>
      <facilityID>SF-013259</facilityID>
      <hl7Message>{xml.sax.saxutils.escape(HL7)}</hl7Message>
    </submitSingleMessage>
  </soap:Body>
</soap:Envelope>"""
headers = {
    "Content-Type": (
        'application/soap+xml; charset=utf-8; action="urn:cdc:iisb:2011:submitSingleMessage"'
    )
}
start = time.time()
try:
    response = requests.post(URL, data=body.encode("utf-8"), headers=headers, timeout=90)
    print(f"{time.time() - start:.2f}s status={response.status_code}")
    print(response.text[:1200])
except Exception as exc:
    print(f"{time.time() - start:.2f}s error={type(exc).__name__}: {exc}")
