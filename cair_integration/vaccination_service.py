"""CAIR submission flow using existing ClaudMD tables.

The EMR application is responsible for:
  1. Setting EHRHeaders.IsPublish = true when the visit is finalized
  2. Creating a row in EHRVaccineThirdPartySubmissions per vaccine (SubmitStatus = 0)

The background service only reads and updates these tables.
"""

# No insert helpers here — submissions are created by ClaudMD when a visit is published.
