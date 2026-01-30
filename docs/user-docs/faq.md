# Frequently Asked Questions (FAQ)

This section addresses common questions

**Q: How does pseudonymization work in ADIT?**

A: ADIT uses the dicognito library to:

- **Remove identifying information** from DICOM headers
- **Replace patient names/IDs** with provided pseudonyms
- **Add trial information** if specified
- **Maintain consistency** across multiple studies for the same patient

**Q: What DICOM tags are anonymized?**

A: ADIT anonymizes standard identifying tags including:

- Patient Name, Patient ID, Patient Birth Date
- Referring Physician, Institution Name
- Other tags according to DICOM anonymization profiles

The following date/time tags are preserved to maintain clinical context:

- Study Date, Study Time
- Series Date, Series Time
- Acquisition Date/Time
- Content Date/Time

**Q: Does ADIT preserve patient age during anonymization?**

A: Yes. While PatientBirthDate is anonymized (shifted by a random offset), ADIT uses the dicognito library which preserves the patient's age relative to the study date. This means an 80-year-old patient will still appear as 80 years old in the anonymized data, not as a 20-year-old. This is important for maintaining clinically relevant information while protecting patient identity.

**Q: Which DICOM protocols are supported for my server?**

To determine which DICOM protocols are supported by a server, consult the server's DICOM Conformance Statement.
