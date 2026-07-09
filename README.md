# CloudDrive

CloudDrive is a production-style cloud storage platform inspired by how
services like Google Drive separate file transfer, metadata management,
and background processing.

Instead of routing uploads through the backend, authenticated clients
upload directly to Amazon S3 using presigned URLs while FastAPI manages
authentication, permissions, metadata, and asynchronous image processing
through event-driven AWS Lambda functions.

The project was built to explore scalable file storage architecture,
event-driven processing, cloud infrastructure, and secure object
handling using FastAPI, PostgreSQL, Docker, and AWS.

------------------------------------------------------------------------

## 🔗 Live Demo

**Backend API:** https://api.clouddrive.world\
**Live Site:** https://clouddrive.world/\
**API Documentation:** https://api.clouddrive.world/docs

------------------------------------------------------------------------

## Screenshots

![Multi-file upload
tracking](screenshots/each_file_independt_upload_track_on_upload_menu.png)

![Home - grid view with image
previews](screenshots/home_with_image_preview_grids.png)

![List view with hover preview](screenshots/list_view_preview.png)

![Sorting options](screenshots/previews_sorting_options_grid.png)

------------------------------------------------------------------------

# Architecture Overview

CloudDrive separates authentication, file transfer, metadata management,
and background processing so each component can scale independently
while keeping user-facing requests lightweight.

    User Browser
          |
          | HTTPS
          v
    Frontend (React + Vite + Tailwind)
          |
          | API Requests
          v
    Application Load Balancer
          |
          | Health Checked Routing
          v
    FastAPI Backend (Docker on EC2)
          |
          |----------------------|
          |                      |
          v                      v
    PostgreSQL            AWS Infrastructure
    (Database)                  |
                                 |
                   -----------------------------
                   |                           |
                   v                           v
              S3 Storage                Secrets Manager

                   |
                   | S3 Event Notifications
                   v

            AWS Lambda Processing
                   |
                   |
          Image Validation + Thumbnails

# Upload Flow

CloudDrive separates authentication from file transfer to avoid routing
large uploads through the application server.

    1. User authenticates with FastAPI
    2. Backend verifies permissions
    3. Backend generates an S3 presigned URL
    4. Browser uploads directly to S3
    5. S3 triggers an AWS Lambda function
    6. Lambda validates the uploaded file
    7. Image previews are generated (when applicable)
    8. PostgreSQL metadata is updated
    9. Processed files become available to the user

This architecture keeps API requests lightweight while allowing storage
and background processing to scale independently.

------------------------------------------------------------------------

# Core Features

## Secure File Uploads

CloudDrive uses AWS S3 presigned URLs so users upload files directly to
object storage instead of routing large file transfers through the
backend API.

Benefits: - Reduces API server bandwidth usage - Allows efficient
large-file uploads - Keeps authentication and authorization handled by
FastAPI

Implemented features: - Parallel multi-file uploads - File metadata
tracking - Folder organization - File deletion and renaming - Image
preview generation

## Authentication and Authorization

Implemented: - JWT-based authentication - bcrypt password hashing -
Password reset workflow - Protected file operations - File and folder
sharing permissions

Users can share files and folders, assign view/edit permissions, and
access shared resources securely.

------------------------------------------------------------------------

# Asynchronous Image Processing

Image processing is handled asynchronously through AWS Lambda functions
triggered by S3 upload events.

Instead of blocking the upload request while generating thumbnails, the
backend confirms the upload immediately and processing occurs in the
background.

## ProfilePictureValidator

Trigger:

`S3 upload → profile_photos/original/`

Responsibilities: 1. Downloads uploaded image 2. Validates actual file
type from binary signatures 3. Rejects malicious or invalid uploads 4.
Resizes valid images to 400×400 5. Stores processed output

Security improvement:

The system does not trust file extensions or client-provided MIME types.
Uploaded files are inspected using their binary signatures before
processing to prevent disguised executable or archive files from being
accepted as valid images.

Performance:

`512ms → 139ms (3.7× improvement)`

## VerifyFilesAndCreatePreviews

Trigger:

`S3 upload → files/{user_id}/{file_id}`

Responsibilities: 1. Extracts file metadata from S3 events 2. Confirms
upload completion in PostgreSQL 3. Generates image thumbnails 4. Updates
processing state

Configuration: - Memory: 512MB - Timeout: 8 seconds - Runtime: Python
3.12

Performance:

`6223ms → 1399ms (4.4× improvement)`

Authentication:

Lambda functions authenticate requests to the backend using a shared
secret stored in AWS Secrets Manager and transmitted through the
`X-Lambda-Secret` header.

This prevents unauthorized services from invoking internal processing
endpoints.

# Reliability

CloudDrive tracks upload state independently from background processing.

If image processing fails, uploaded files remain stored while their
processing status reflects the failure instead of blocking the original
upload request.

This separation keeps uploads fast while isolating long-running
background work from user-facing request latency.

------------------------------------------------------------------------

# Infrastructure

-   Dockerized FastAPI on EC2
-   AWS Application Load Balancer (HTTPS termination, health checks,
    Multi-AZ)
-   AWS S3 object storage with presigned uploads
-   Event-driven AWS Lambda processing
-   AWS Secrets Manager for runtime secrets

# Design Decisions

## Why S3 presigned URLs?

Uploading large files through the backend would consume unnecessary
server bandwidth. Presigned URLs allow clients to upload directly to S3
while the backend continues handling authentication, permissions, and
metadata.

## Why asynchronous processing?

Thumbnail generation and validation can take longer than normal API
requests. Moving processing into Lambda allows faster upload responses,
better user experience, and independent scaling of background workloads.

## Why Lambda instead of FastAPI background tasks?

Lambda provides isolated execution triggered by storage events,
preventing long-running processing from affecting API latency.

## Why Docker?

Docker provides consistent deployment between local development and AWS
while simplifying dependency management.

# Technologies

**Backend:** FastAPI, Python, PostgreSQL, asyncpg

**Cloud:** EC2, S3, Lambda, Application Load Balancer, IAM, Secrets
Manager, CloudWatch

**DevOps:** Docker, Docker Compose, GitHub Actions

**Testing:** pytest

# Testing

Unit and integration tests are written using `pytest`.

Current coverage: **84%**

The test suite validates authentication, permissions, upload workflows,
database operations, and API behavior.

# Deployment

-   EC2 running Docker containers
-   Application Load Balancer with HTTPS
-   S3 object storage
-   Lambda event processing
-   Secrets Manager configuration
-   GitHub Actions CI/CD

Every push triggers automated testing through GitHub Actions.

# Local Development

``` bash
docker-compose up
```

API: http://localhost:8000

Docs: http://localhost:8000/docs

# Future Improvements

-   [ ] Search functionality
-   [ ] File versioning
-   [ ] Batch operations
-   [ ] Video thumbnail generation
-   [ ] Real-time notifications
-   [ ] Rate limiting
-   [ ] Redis caching layer
-   [ ] Background job retries

# Contact

Built by Mauricio Moreno

GitHub: https://github.com/mauricio0129
