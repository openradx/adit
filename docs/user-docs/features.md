# Features

ADIT provides a comprehensive set of features for DICOM data management and transfer.

### DICOM Server Integration

- ✅ **Multiple Server Support**: Connect to multiple DICOM servers simultaneously
- ✅ **Protocol Support**: Both DIMSE and DICOMweb protocols
- ✅ **Server Configuration**: Web-based admin interface for server setup
- ✅ **Mixed Protocol Support**: Servers can support different combinations of protocols

### Data Transfer

- ✅ **Selective Transfer**: Transfer specific studies between DICOM servers
- ✅ **Batch Transfer**: Handle multiple studies in batch operations from CSV/Excel files
- ✅ **Batch Query**: Query multiple studies using uploaded CSV/Excel files
- ✅ **Series Selection**: Transfer specific series within a study
- ✅ **Resume Capability**: Automatic handling of interrupted transfers

### Pseudonymization

- ✅ **Basic Pseudonymization**: Assign pseudonym names to patients during transfer
- ✅ **Trial Protocol Support**: Add trial protocol ID and name to transferred studies
- ✅ **Permission Control**: Control who can transfer unpseudonymized data
- ✅ **Integration with dicognito**: Uses dicognito library for DICOM anonymization

### Web Interface

- ✅ **Dashboard**: User-friendly web interface for all operations
- ✅ **DICOM Explorer**: Browse and search DICOM studies on servers
- ✅ **Progress Monitoring**: Real-time transfer status and progress updates
- ✅ **User Management**: Role-based access control interface
- ✅ **Interactive Forms**: Dynamic web forms with HTMX

### Batch Operations

- ✅ **CSV/Excel Import**: Upload batch files for queries and transfers
- ✅ **Template Support**: Download template files for batch operations
- ✅ **Validation**: Pre-validate batch operations before execution
- ✅ **Error Handling**: Comprehensive error reporting with line numbers
- ✅ **Progress Tracking**: Individual task status within batch jobs

### Priority System

- ✅ **Job Prioritization**: Mark jobs as urgent for higher priority processing
- ✅ **Queue Management**: Manage transfer queues with different priorities
- ✅ **Permission Control**: Control who can create urgent jobs.

### API Access

- ✅ **DICOMweb API**: Complete DICOMweb implementation (QIDO-RS, WADO-RS, STOW-RS)
- ✅ **Token Authentication**: Secure API access with Django tokens
- ✅ **Python Client**: Available in separate adit-client package

### Access Control

- ✅ **User Management**: Multi-user support with Django authentication
- ✅ **Group-based Permissions**: Fine-grained server access by user groups
- ✅ **Server Permissions**: Control source/destination access per user
- ✅ **Activity Logging**: Track all user activities and transfers
- ✅ **Session Management**: Secure session handling

## Technical Capabilities

### Supported Protocols

- ✅ **DICOM DIMSE**: Full C-FIND, C-MOVE, C-GET, C-STORE support
- ✅ **DICOMweb**: QIDO-RS, WADO-RS, STOW-RS implementation
- ✅ **Transfer Syntaxes**: Multiple DICOM transfer syntax support
- ✅ **Compression**: Support for various DICOM compression formats

### Performance

- ✅ **Async Processing**: Background task processing with Procrastinate
- ✅ **Parallel Operations**: Multi-threaded transfer operations
- ✅ **Resource Management**: Configurable worker allocation
- ✅ **PostgreSQL Backend**: Reliable PostgreSQL-based task queue

### Monitoring

- ✅ **Job Status Tracking**: Detailed status for all jobs and tasks
- ✅ **Error Reporting**: Comprehensive error logging and reporting
- ✅ **WebSocket Updates**: Real-time status updates via Django Channels
- ✅ **Audit Trails**: Complete logging of all operations

### File Handling

- ✅ **Temporary File Management**: Automatic cleanup of temporary files
- ✅ **Large File Support**: Streaming support for large DICOM files
- ✅ **Format Support**: CSV and Excel file parsing with pandas

## 💡 Feature Requests

Have an idea for a new feature? Please submit a feature request on the [GitHub repository](https://github.com/openradx/adit/issues).
