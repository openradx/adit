# Architecture Overview

This document provides an overview of ADIT's architecture and key components.

## Technology Stack

### Backend Framework

- **Django 5.1+**: Web framework providing MVC architecture, ORM, and admin interface
- **Python 3.12+**: Modern Python with type hints and async support
- **PostgreSQL**: Primary database for relational data storage
- **Procrastinate**: Background task queue for asynchronous job processing
- **Docker**: Containerization for consistent deployment environments

### Frontend Technology

- **Django Templates**: Server-side rendering with template inheritance
- **HTMX**: Dynamic frontend interactions without complex JavaScript frameworks
- **Bootstrap 5**: Responsive CSS framework for consistent UI
- **FontAwesome**: Icon library for consistent iconography

### DICOM Integration

- **pydicom**: Core DICOM file parsing and manipulation
- **pynetdicom**: DICOM networking (C-FIND, C-MOVE, C-STORE operations)
- **DICOMweb**: RESTful DICOM services integration
- **Custom DICOM utilities**: Pseudonymization, validation, and transfer logic

## Application Architecture

### Core Django Apps Structure

#### **Core App** (`adit.core`)

- **Purpose**: Foundation services and shared components
- **Components**: User management, DICOM node configuration, base models, utilities
- **Key Features**: Authentication, authorization, DICOM server management

#### **Transfer Apps**

- **Batch Transfer** (`adit.batch_transfer`): Bulk data transfer operations
- **Selective Transfer** (`adit.selective_transfer`): Individual study transfers
- **Batch Query** (`adit.batch_query`): Bulk DICOM server queries

#### **Exploration & Discovery**

- **DICOM Explorer** (`adit.dicom_explorer`): Interactive DICOM data browsing
- **DICOM Web** (`adit.dicom_web`): RESTful DICOM services interface

## Authentication & Authorization

- **Django Auth System**: Built-in user authentication
- **Group-based Permissions**: Fine-grained access control
- **DICOM Node Access**: Server-specific user permissions
- **Session Management**: Secure session handling

## Data Architecture

### **Primary Models**

- **Users & Groups**: Authentication and authorization
- **DICOM Nodes**: Server configurations and capabilities
- **Transfer Jobs**: Batch and selective transfer operations
- **Tasks**: Individual transfer units with status tracking

## Performance Considerations

### **Asynchronous Processing**

- Background job processing for long-running operations
- Non-blocking user interface during transfers
- Scalable worker processes

This architecture supports ADIT's mission of providing reliable, secure, and user-friendly DICOM data exchange capabilities while maintaining flexibility for future enhancements and integrations.
