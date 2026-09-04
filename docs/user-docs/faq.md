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
- Frame Reference Date/Time

**Q: Does ADIT preserve patient age during anonymization?**

A: Only approximately. dicognito shifts all dates in the data set backwards by a random offset between 62 and 730 days, including the PatientBirthDate. ADIT keeps the study, series, acquisition, content and frame reference dates and times unchanged (see above) to preserve the clinical timeline. As a consequence, an age calculated from the anonymized birth date and the original study date is between 2 months and 2 years higher than the real age. A PatientAge tag in the header is not modified. If the exact age matters for your analysis, record it before the transfer (e.g. with a batch query).

**Q: Which DICOM protocols are supported for my server?**

A: To determine which DICOM protocols are supported by a server, consult the server's DICOM Conformance Statement.
