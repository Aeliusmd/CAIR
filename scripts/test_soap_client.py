"""Quick SOAP connectivity test against CAIR stage."""
from cair_integration.cair.soap_client import CairSoapClient
from cair_integration.config import get_settings

settings = get_settings()
client = CairSoapClient(
    settings.cair_soap_url,
    settings.cair_soap_username,
    settings.cair_soap_password,
    settings.sending_facility_id,
)
hl7 = (
    "MSH|^~\\&|ClaudMD|SF-013259||CAIR2|20260101120000||VXU^V04^VXU_V04|"
    "test-soap-fix|P|2.5.1|||AL|AL|||||Z22^CDCPHINVS|SF-013259\r"
)
result = client.send_vxu(hl7)
print("success:", result.success)
print("ack_code:", result.ack_code)
print("error:", (result.error_details or "")[:800])
print("raw:", (result.raw_response or "")[:800])
