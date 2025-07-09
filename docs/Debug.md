# DCMTK Debugging Guide

This document provides a generic guide for debugging DICOM operations using DCMTK tools. Currently, it includes instructions for performing C-GET operations.

---

## Debugging DICOM Operations with DCMTK

### C-GET Operations

The C-GET operation allows you to retrieve DICOM studies or images from a PACS server. Follow the steps below to perform and debug C-GET operations:

### Steps

1. **SSH into the Server Running ADIT**:

   - Connect to the server running ADIT, which is linked to the PACS server, using the following command:

   ```bash
   ssh <username>@<server_ip>
   ```

   - Ensure you have access to the PACS server and know its IP address, port, and AE title.

2. **Retrieve a Study Using C-GET**:

   - Use the following command to retrieve a study:

     ```bash
     getscu -v -aet <CALLING_AE_TITLE> -aec <CALLED_AE_TITLE> \
     -k 0008,0052=STUDY \
     -k 0020,000D=<STUDY_INSTANCE_UID> \
     -od ./received_files <PACS_IP> <PACS_PORT>
     ```

3. **Retrieve a Specific Image**:

   - Use this command to retrieve a specific image:

     ```bash
     getscu -v -aet <CALLING_AE_TITLE> -aec <CALLED_AE_TITLE> \
     -k 0008,0052=IMAGE \
     -k 0008,0018=<SOP_INSTANCE_UID> \
     -od ./received_files <PACS_IP> <PACS_PORT>
     ```

---

### Notes

- Replace `<CALLING_AE_TITLE>`, `<CALLED_AE_TITLE>`, `<STUDY_INSTANCE_UID>`, `<SOP_INSTANCE_UID>`, `<PACS_IP>`, and `<PACS_PORT>` with the appropriate values for your setup.
- Ensure the `getscu` tool from DCMTK is installed and properly configured on your system.
- Use the `-v` flag for verbose output to help debug issues during the operation.
- The `-od` option specifies the output directory where the retrieved files will be saved.

---

### Troubleshooting

- **Connection Issues**:

  - Verify the PACS server's IP address and port are correct.
  - Ensure the AE titles match the configuration on the PACS server.

- **Failed Sub-operations**:

  - Check the verbose output for details about failed sub-operations.
  - Inspect the PACS server logs for additional information.

- **Invalid Query Parameters**:
  - Ensure the DICOM tags used in the query (`0008,0052`, `0020,000D`, `0008,0018`) are correct and match the PACS server's expectations.

---

This guide will be expanded to include other DCMTK tools and operations in the future.
