# MA Provider Directory Requirements for Contract Year 2027

## Two Approved Approaches

For Contract Year 2027, MA organizations can supply provider directory data using either:

1. **Machine-Readable JSON Files** (temporary solution)
2. **FHIR-Based JSON API Files** (long-term solution)

---

## Option 1: Machine-Readable JSON Files

### General Requirements for non-FHIR JSON

- [ ] Files must be publicly accessible via URLs
- [ ] Must include a pre-processed index file at the primary URL
- [ ] Index file must provide all constituent file URLs
- [ ] Must implement HTTP metadata (ETag, Last-Modified headers)
- [ ] Support conditional requests (If-None-Match, If-Modified-Since)
- [ ] Files must be updated within 30 days of changes

### Required Fields - All Entries

#### Core Fields (Required for ALL providers/facilities)

- [ ] **npi**: 10-digit National Provider Identifier
- [ ] **type**: Must be "Individual" or "Facility"
- [ ] **plans**: Array of unique MA plans (see Plans Sub-Type)
- [ ] **lastUpdatedOn**: ISO 8601 format (YYYY-MM-DD)

### Required Fields - Individual Providers

#### Name Object (Required)

- [ ] **name.first**: Full first name
- [ ] **name.last**: Full last name
- [ ] **name.prefix**: One of: Mr., Mrs., Miss, Ms., Dr. (optional)
- [ ] **name.middle**: Full middle name (optional)
- [ ] **name.suffix**: One of: Jr., Sr., II, III, IV (optional)

#### Additional Individual Fields

- [ ] **sex**: Male or Female (optional)
- [ ] **languages**: Array of languages spoken

### Required Fields - Facilities

- [ ] **facilityName**: Name of the facility
- [ ] **facilityType**: Array using NUCC taxonomy codes

### Plans Sub-Type (Required for all entries)

- [ ] **maPlanId**: Format: [Contract#]-[Plan ID]-[Segment ID] (e.g., H9999-001-001)
- [ ] **year**: Contract year for which data applies
- [ ] **addresses**: List of addresses (see Address Sub-Type)
- [ ] **specialty**: Array using NUCC taxonomy codes
- [ ] **accepting**: "Accepting" or "Not Accepting" (optional)
- [ ] **networkId**: Unique identifier of network (optional)

### Address Sub-Type (Required)

- [ ] **address**: Street address
- [ ] **address2**: Street address 2 (optional)
- [ ] **city**: City name
- [ ] **state**: Two-letter state abbreviation (e.g., MD)
- [ ] **zip**: Five-digit zip code (as string)
- [ ] **phone**: 10-digit phone number (e.g., 1112223333)

### Data Integrity Rules

- [ ] If provider/facility has multiple NPIs, create separate entries for each
- [ ] Use role-based hierarchy
- [ ] If specialty coverage varies by location, create separate entries for each specialty/location combination
- [ ] Include ONLY current in-network providers and facilities

---

## Option 2: FHIR-Based JSON API Files

### General Requirements for FHIR json

- [ ] Must conform to PDex Plan-Net Implementation Guide v1.2.0
- [ ] Built on HL7® FHIR release 4 standard
- [ ] Files must be publicly accessible (no authentication required)
- [ ] Must be JSON-based (XML-based FHIR not supported)
- [ ] Must include a pre-processed index file at primary URL
- [ ] Must implement HTTP metadata (ETag, Last-Modified headers)
- [ ] Support conditional requests
- [ ] Files must be updated within 30 days of changes

### Required FHIR Resources

- [ ] **InsurancePlan**
- [ ] **Location**
- [ ] **Organization** (Network)
- [ ] **Organization** (Facility)
- [ ] **OrganizationAffiliation**
- [ ] **Practitioner**
- [ ] **PractitionerRole**

---

## Individual Provider Requirements (FHIR)

### PractitionerRole Resource

- [ ] **Identifier (NPI)**: `PractitionerRole.identifier[system='http://hl7.org/fhir/sid/us-npi'].value` OR `Practitioner.identifier[system='http://hl7.org/fhir/sid/us-npi'].value`
- [ ] **Date Record Last Updated**: `PractitionerRole.meta.lastUpdated`
- [ ] **Location**: `PractitionerRole.location` (separate Location resource for each address)
- [ ] **Practitioner Specialty**: `specialty.coding.code` (array of NUCC individual codes)
- [ ] **Accepts New Patients**: `PractitionerRole.extension[url='http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/newpatients']` (optional)
  - Accepting: "newpt"
  - Not accepting: "not" or "existptonly"
- [ ] **Network**: `PractitionerRole.network` (links to InsurancePlan)

### Practitioner Resource

- [ ] **Identifier (NPI)**: Same as PractitionerRole
- [ ] **Practitioner Name**: `Practitioner.name`
  - [ ] **Full Name**: `Practitioner.name.text`
  - [ ] **Prefix**: `Practitioner.name.prefix` (optional)
  - [ ] **First Name**: `Practitioner.name.given[0]`
  - [ ] **Middle Name**: `Practitioner.name.given[1]` (optional)
  - [ ] **Last Name**: `Practitioner.name.family`
  - [ ] **Suffix**: `Practitioner.name.suffix` (optional)
- [ ] **Phone Number**: `PractitionerRole.telecom[system='phone'].value` OR `Practitioner.telecom[system='phone'].value`
- [ ] **Sex**: `Practitioner.gender` (optional)
- [ ] **Languages Spoken**: `Practitioner.communication.coding.code` (array)

### Location Resource (for Practitioners)

- [ ] **ID**: `Location.id`
- [ ] **Street Address 1**: `Location.address.line[0]`
- [ ] **Street Address 2**: `Location.address.line[1]` (optional)
- [ ] **City**: `Location.address.city`
- [ ] **State**: `Location.address.state`
- [ ] **Zip Code**: `Location.address.postalCode`

### InsurancePlan Resource (for Practitioners)

- [ ] **CMS MA Plan Identifier**: `InsurancePlan.identifier[system='http://cms.gov/medicare/ma-plan-id']`
  - Format: [Contract#]-[Plan ID]-[Segment ID]
  - Use 000 for non-segmented plans
  - Example: H9999-001-001
- [ ] **Contract Year**: `InsurancePlan.period` (year will be extracted)
- [ ] **Network ID**: `InsurancePlan.network` (links to PractitionerRole)

---

## Facility Requirements (FHIR)

### Organization Resource (Facility)

- [ ] **Type Requirements**:
  - `Organization.type.coding.system = 'http://hl7.org/fhir/us/davinci-pdex-plan-net/CodeSystem/OrgTypeCS'`
  - `Organization.type.coding.code = 'fac'`
- [ ] **Identifier (NPI)**: `Organization.identifier[system='http://hl7.org/fhir/sid/us-npi'].value`
- [ ] **Date Record Last Updated**: `Organization.meta.lastUpdated`
- [ ] **Facility Name**: `Organization.name`
- [ ] **Facility Type**: `Organization.type.coding.code`
- [ ] **Facility Location**: `Organization.address` OR `Location.address`
  - [ ] **Street Address 1**: `address.line[0]`
  - [ ] **Street Address 2**: `address.line[1]` (optional)
  - [ ] **City**: `address.city`
  - [ ] **State**: `address.state`
  - [ ] **Zip Code**: `address.postalCode`

### OrganizationAffiliation Resource

- [ ] **Network**: `OrganizationAffiliation.Network` (links to InsurancePlan)
- [ ] **Organization**: `OrganizationAffiliation.Organization` (links to Organization)
- [ ] **Location**: `OrganizationAffiliation.Location` (separate instance for each address)
- [ ] **Specialty**: `OrganizationAffiliation.specialty.coding.code` (array of NUCC non-individual codes)

### InsurancePlan Resource (for Facilities)

- [ ] **CMS MA Plan Identifier**: `InsurancePlan.identifier[system='http://cms.gov/medicare/ma-plan-id']`
  - Format: [Contract#]-[Plan ID]-[Segment ID]
  - Use 000 for non-segmented plans
  - Example: H9999-001-001
- [ ] **Contract Year**: `InsurancePlan.period`
- [ ] **Network ID**: `InsurancePlan.network` (links to OrganizationAffiliation)

---

## Common Data Integrity Rules (Both Approaches)

- [ ] If provider/facility has multiple NPIs, create separate resource entries for each
- [ ] Each address must be represented in its own Location resource instance
- [ ] Include ONLY current in-network providers and facilities
- [ ] Ensure clear relationship between provider/facility and unique MA plan (Contract#-Plan ID-Segment ID)
- [ ] All specialty codes must use NUCC taxonomy codes

---

## HTTP Metadata Requirements (Both Approaches)

### HEAD Method Support

- [ ] Support HEAD method for JSON resources
- [ ] Include ETag (weak validator acceptable)
- [ ] Include Last-Modified header
- [ ] Include Content-Length header
- [ ] Include Content-Type header

### Conditional Request Support

- [ ] Support If-None-Match header
- [ ] Support If-Modified-Since header
- [ ] Return 304 Not Modified when resource unchanged

### GET Request Headers

- [ ] Include ETag (weak validator acceptable, e.g., W/"abc123")
- [ ] Include Last-Modified (reflect most recent meaningful update)
- [ ] Include Content-Length (accurate byte count)
- [ ] Include Content-Type

---

## HPMS Requirements (Both Approaches)

- [ ] Enter and maintain provider directory API URLs in HPMS
- [ ] Define URLs by contract year/contract number
- [ ] Specify whether using machine-readable JSON or FHIR-based API
- [ ] Complete annual attestation by authorized official (CEO, CFO, or COO)
- [ ] Attestation deadline: September 1, 2026 (for CY 2027)

---

## Validation Requirements (Both Approaches)

CMS will validate:

- [ ] API URLs are functional and accessible
- [ ] Files adhere to technical specifications
- [ ] Data adheres to field-level specifications
- [ ] Records exist for all individual (not employer-only) plan/segments
- [ ] Directory updated at least every 30 days

---

## Important Notes

1. **Machine-Readable JSON is temporary**: All MA plans expected to migrate to FHIR-based APIs for National Provider Directory
2. **Only current in-network providers**: Do not include terminated or out-of-network providers
3. **Testing period**: May 4 - August 31, 2026
4. **Production deadline**: September 18, 2026 (target for production-ready CY 2027 data)
5. **Production release**: October 1, 2026
