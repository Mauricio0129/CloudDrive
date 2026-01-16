# CloudDrive

A file storage API built with FastAPI, PostgreSQL, and AWS S3. Features user authentication, parallel multi-file uploads, automatic image processing, and file sharing.

## 🔗 Live Demo

**Backend API:** https://api.clouddrive.world  
**Live Site:** https://clouddrive.world/  
**API Documentation:** https://api.clouddrive.world/docs

## Why I Built This

I wanted to build a real, deployed system rather than following tutorials. CloudDrive gave me hands-on experience with AWS infrastructure, event-driven architecture, and performance optimization. It pushed me to think about reliability (health checks, load balancing across availability zones), security (presigned URLs, file validation), and user experience (automatic thumbnails, parallel uploads).

## Overview

CloudDrive is a REST API for file storage. Users can upload multiple files simultaneously to AWS S3, organize them in folders, and share files with permissions.

**Key capabilities:**
- Parallel multi-file uploads with S3 presigned URLs
- Folder-based organization with sharing controls
- JWT authentication with bcrypt password hashing
- AWS deployment with Application Load Balancer across availability zones
- Automatic image processing (see Lambda Functions section)

## Features

### Authentication
- User registration and login
- JWT token-based authentication
- Password hashing with bcrypt
- Secure password reset flow

### File Operations
- Parallel multi-file uploads using S3 presigned URLs
- File metadata tracking (name, size, MIME type, upload date)
- Folder-based organization
- File deletion and renaming
- Image preview endpoints

### Profile Management
- Profile photo uploads
- Automatic resizing and validation

### Sharing
- Share files or folders with other users
- Permission levels (view, edit)
- View all items shared with you

## Architecture

```
┌─────────────┐
│ User/Browser│
└──────┬──────┘
       │ HTTPS
       ↓
┌──────────────────────────────┐
│ Frontend (Vercel)            │
│ React + Vite + Tailwind      │
└──────┬───────────────────────┘
       │ API Calls
       ↓
┌──────────────────────────────┐
│ Application Load Balancer    │
│ api.clouddrive.world         │
│                              │
│ - SSL/TLS Termination        │
│ - Health Check: /health      │
│ - AZ: us-east-1a, us-east-1f │
└──────┬───────────────────────┘
       │ Forwards to EC2
       ↓
┌──────────────────────────────────────────────┐
│ EC2 Instance (Ubuntu)                        │
│                                              │
│ ┌──────────────────────────────────────┐     │
│ │ Docker Container                     │     │
│ │ FastAPI (uvicorn app.main:app)       │     │
│ └──────────────────────────────────────┘     │
│                                              │
│ ┌──────────────────────────────────────┐     │
│ │ IAM Role                             │     │
│ │ - S3 Access (cloudriveproject only)  │     │
│ │ - SecretsManagerReadWrite            │     │
│ └──────────────────────────────────────┘     │
└──────┬────────────┬──────────────────────────┘
       │            │
       ↓            ↓
┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│AWS Secrets  │  │  AWS S3     │  │  Supabase    │
│Manager      │  │  Bucket     │  │  PostgreSQL  │
└─────────────┘  └──────┬──────┘  └──────────────┘
                        │
                        │ S3 Event Triggers
                        ↓
              ┌─────────────────────────────┐
              │ AWS Lambda Functions        │
              │ - ProfilePictureValidator   │
              │ - VerifyFilesAndCreate      │
              │   Previews                  │
              └─────────────────────────────┘
```

## Lambda Functions

CloudDrive uses two Lambda functions triggered by S3 events to handle image processing asynchronously.

### ProfilePictureValidator
**Trigger:** S3 upload to `profile_photos/original/`

Validates and processes user profile pictures. Downloads the file, checks the actual file type from bytes (not extension), and either deletes malicious uploads or resizes valid images to 400×400.

**Security feature:** Prevents users from uploading `.exe`, `.zip`, or other non-image files by detecting MIME types from file bytes rather than trusting file extensions.

**Flow:**
1. Download file from S3 and detect type from bytes
2. If not an image → delete from S3 and exit
3. If valid image → resize to 400×400 with PIL → upload to `resized/` folder → notify backend

**Performance:** Optimized from 512ms → **139ms** (3.7× faster)

---

### VerifyFilesAndCreatePreviews
**Trigger:** S3 upload to `files/{user_id}/{file_id}`

Confirms file uploads in the database and automatically generates 400×400 thumbnails for images.

**Flow:**
1. Parse S3 key to extract `user_id` and `file_id`
2. Notify backend to set `confirmed_upload = TRUE` in database
3. If file is an image → generate 400×400 thumbnail with PIL → upload to `previews/` folder → notify backend to set `preview_ready = TRUE`

**Configuration:** 512MB memory, 8 second timeout, Python 3.12

**Performance:** Optimized from 6223ms → **1399ms** (4.4× faster) by increasing memory from 128MB to 512MB

**Authentication:** Both Lambda functions authenticate with the backend API using a shared secret in the `X-Lambda-Secret` header.

**Why asynchronous?** Processing images after upload keeps the upload endpoint fast. Users get immediate feedback while thumbnails generate in the background.

## API Endpoints

### Authentication
- `POST /register` - Create new user
- `POST /login` - Authenticate and get JWT token
- `POST /request-password-reset` - Request password reset email
- `POST /reset-password` - Reset password with token

### Files
- `POST /files` - Request S3 presigned URLs for upload
- `GET /files` - List user's files
- `PATCH /files/{file_id}` - Rename file
- `DELETE /files/{file_id}` - Delete file
- `GET /image-preview/{file_id}` - Get image thumbnail

### Folders
- `POST /drive` - Create folder
- `GET /drive` - List root contents
- `GET /drive/{folder_id}` - List folder contents
- `PATCH /drive/{folder_id}` - Rename folder

### Sharing
- `POST /share` - Share file or folder
- `GET /shared-with-me` - List shared items

### Profile
- `POST /profile-photo` - Upload profile photo
- `GET /profile-photo` - Get profile photo URL

### Health
- `GET /` - API info
- `GET /health` - Health check

## Getting Started

### Prerequisites
- Docker
- AWS account (S3, EC2, Lambda, IAM)
- PostgreSQL database

### Run Locally
```bash
docker-compose up
# API available at http://localhost:8000
# Docs available at http://localhost:8000/docs
```

## Testing

```bash
pytest tests/unit_tests
# Coverage: 84%
```

## Deployment

Deployed on AWS with:
- **EC2** running Docker container
- **Application Load Balancer** with SSL certificate, health checks, and availability zone redundancy (us-east-1a, us-east-1f)
- **S3** for file storage with event triggers
- **Lambda Functions** for image processing
- **Secrets Manager** for credentials

### CI/CD
GitHub Actions runs tests on every push.

## What I Learned

### AWS
- EC2 server deployment and Docker hosting
- Application Load Balancer with SSL termination, health checks, and availability zone distribution
- S3 object storage, event notifications, and presigned URLs
- Lambda event-driven processing and performance tuning
- Secrets Manager and IAM role-based access control

### Backend
- FastAPI framework and async Python
- RESTful API design and JWT authentication
- Password hashing with bcrypt
- Error handling and HTTP status codes

### Database
- PostgreSQL schema design
- Async operations with asyncpg
- Boolean flags for tracking async processing state

### DevOps
- Docker containerization and Docker Compose
- GitHub Actions CI/CD
- Availability zone redundancy within AWS region

### Performance
- Lambda memory tuning (4.4× speedup on image processing)
- PIL/Pillow optimization
- Async/await patterns

## Future Improvements

- [ ] Search functionality
- [ ] File versioning
- [ ] Batch operations
- [ ] Video preview thumbnails
- [ ] Real-time notifications
- [ ] Rate limiting
- [ ] Caching layer (Redis)

## Contact

Built by Mauricio Moreno  
GitHub: [@mauricio0129](https://github.com/mauricio0129)
