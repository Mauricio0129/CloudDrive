# CloudDrive

A file storage API built with FastAPI, PostgreSQL, and AWS S3. Supports user authentication, parallel multi-file uploads, automatic image processing (profile photos + file previews), and file sharing with permissions.

## 🔗 Live Demo

**Backend API:** https://api.clouddrive.world  
**Live Site:** https://clouddrive.world/
**API Documentation:** https://api.clouddrive.world/docs

## Architecture

```
┌─────────────┐
│ User/Browser│
└──────┬──────┘
       │
       │ HTTPS
       ↓
┌──────────────────────────────────────────────┐
│ Frontend (Vercel)                            │
│ https://frontend-bb5s5p6zk-mauricio.vercel...│
│                                              │
│ - React + Vite                               │
│ - Tailwind CSS                               │
│ - Consumes CloudDrive API                    │
└──────┬───────────────────────────────────────┘
       │
       │ API Calls (HTTPS)
       ↓
┌──────────────────────────────────────────────┐
│ Application Load Balancer                    │
│ api.clouddrive.world                         │
│                                              │
│ - SSL Certificate (AWS Certificate Manager) │
│ - CNAME: domain → ALB DNS                   │
│ - SSL/TLS Termination (HTTPS → HTTP)        │
│ - Health Check: /health                     │
│ - Listeners: 80 (HTTP), 443 (HTTPS)         │
└──────┬───────────────────────────────────────┘
       │
       │ Target Group
       │ Forwards to EC2 on Port 80 (HTTP)
       ↓
┌──────────────────────────────────────────────────────────┐
│ Security Group Check                                     │
│ (Allow Port 80 from ALB → EC2)                          │
└──────┬───────────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────────┐
│ EC2 Instance (Ubuntu)                                    │
│ CloudDriveBackend                                        │
│                                                          │
│ ┌────────────────────────────────────────────────────┐   │
│ │ Docker Container                                   │   │
│ │ Port Mapping: -p 80:8080                          │   │
│ │                                                    │   │
│ │ ┌────────────────────────────────────────────┐     │   │
│ │ │ FastAPI Application (Port 8080)            │     │   │
│ │ │ (uvicorn app.main:app)                     │     │   │
│ │ └────────────────────────────────────────────┘     │   │
│ └────────────────────────────────────────────────────┘   │
│                                                          │
│ ┌────────────────────────────────────────────────────┐   │
│ │ IAM Role Attached                                  │   │
│ │ - S3 Access (cloudriveproject bucket only)        │   │
│ │ - SecretsManagerReadWrite                         │   │
│ └────────────────────────────────────────────────────┘   │
└──────┬──────────────┬────────────────┬───────────────────┘
       │              │                │
       │              │                │
       ↓              ↓                ↓
┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│AWS Secrets  │  │  AWS S3     │  │  Supabase    │
│Manager      │  │  Bucket     │  │  PostgreSQL  │
│             │  │             │  │  (External)  │
│CloudDrive/  │  │clouddrive   │  │              │
│prod/backend │  │project      │  │  Database:   │
│             │  │             │  │  - users     │
│Stores:      │  │CORS Enabled │  │  - files     │
│- DB creds   │  │for browser  │  │  - folders   │
│- API keys   │  │requests     │  │  - shares    │
│- Secrets    │  │             │  │              │
└──────┬──────┘  └──────┬──────┘  └──────────────┘
       │                │
       │                │ S3 Bucket Structure:
       │                │ ├── profile_photos/
       │                │ │   ├── original/{user_id}/photo
       │                │ │   └── resized/{user_id}/photo.{ext}
       │                │ ├── files/{user_id}/{file_id}
       │                │ └── previews/{user_id}/{file_id}
       │                │
       │                │ S3 Event Triggers:
       │                │ 1. profile_photos/original/* → ProfilePictureValidator
       │                │ 2. files/* → VerifyFilesAndCreatePreviews
       │                ↓
       │    ┌───────────────────────────────────────────────┐
       │    │ AWS Lambda Functions                          │
       │    │                                               │
       │    │ ┌─────────────────────────────────────────┐   │
       │    │ │ 1. ProfilePictureValidator              │   │
       │    │ │                                         │   │
       │    │ │ Trigger: S3 PUT to original/            │   │
       │    │ │                                         │   │
       │    │ │ Process:                                │   │
       │    │ │ 1. Get key from S3 event                │   │
       │    │ │ 2. Download file                        │   │
       │    │ │ 3. Detect file type from bytes          │   │
       │    │ │                                         │   │
       │    │ │ IF NOT IMAGE (.exe, .zip, etc):         │   │
       │    │ │   - Delete from S3                      │   │
       │    │ │   - Exit                                │   │
       │    │ │                                         │   │
       │    │ │ IF IS IMAGE (JPEG/PNG/GIF/WebP):        │   │
       │    │ │   - Resize to 400x400                   │   │
       │    │ │   - Detect actual extension             │   │
       │    │ │   - Upload to resized/ folder           │   │
       │    │ │   - Delete original                     │   │
       │    │ │   - Call /confirm-profile-picture       │   │
       │    │ │     with shared secret                  │   │
       │    │ │                                         │   │
       │    │ │ Performance: 512ms → 139ms              │   │
       │    │ └─────────────────────────────────────────┘   │
       │    │                                               │
       │    │ ┌─────────────────────────────────────────┐   │
       │    │ │ 2. VerifyFilesAndCreatePreviews         │   │
       │    │ │                                         │   │
       │    │ │ Trigger: S3 PUT to files/*              │   │
       │    │ │ Memory: 512MB                           │   │
       │    │ │ Timeout: 8 seconds                      │   │
       │    │ │                                         │   │
       │    │ │ Process:                                │   │
       │    │ │ 1. Parse S3 key: files/{user_id}/{id}   │   │
       │    │ │ 2. Download file from S3                │   │
       │    │ │ 3. Call /confirm-file-upload            │   │
       │    │ │    - Sets confirmed_upload = TRUE       │   │
       │    │ │                                         │   │
       │    │ │ 4. Check if image file                  │   │
       │    │ │    IF IMAGE:                            │   │
       │    │ │    - Generate 400x400 thumbnail         │   │
       │    │ │    - Upload to previews/{user_id}/{id}  │   │
       │    │ │    - Call /confirm-file-preview         │   │
       │    │ │      Sets preview_ready = TRUE          │   │
       │    │ │                                         │   │
       │    │ │ Performance: 6223ms → 1399ms            │   │
       │    │ │ (128MB → 512MB memory optimization)     │   │
       │    │ └─────────────────────────────────────────┘   │
       │    └───────────────────────────────────────────────┘
       │                      │
       │                      │ POST /confirm-file-upload
       │                      │ POST /confirm-file-preview
       │                      │ Header: X-Lambda-Secret: {hex_32}
       │                      ↓
       │              ┌───────────────────────┐
       │              │ Backend:              │
       │              │ - Verify shared secret│
       │              │ - Update database     │
       │              │   confirmed_upload    │
       │              │   preview_ready       │
       │              └───────────────────────┘
       │
       │ Uses for encryption
       ↓
┌─────────────┐
│  AWS KMS    │
│             │
│ aws/secrets │
│ manager_key │
└─────────────┘


┌────────────────────────────────────────────────────────────┐
│ VPC Container (172.31.0.0/16)                              │
│                                                            │
│  ┌──────────────────────────────────────┐                  │
│  │ Internet Gateway (igw-xxx)           │                  │
│  └────────────┬─────────────────────────┘                  │
│               │                                            │
│  ┌────────────▼─────────────────────────┐                  │
│  │ Route Table (rtb-xxx)                │                  │
│  │ - 0.0.0.0/0 → igw-xxx (Internet)     │                  │
│  │ - 172.31.0.0/16 → local (Internal)   │                  │
│  └────────────┬─────────────────────────┘                  │
│               │                                            │
│        ┌──────┴──────┐                                     │
│        │             │                                     │
│  ┌─────▼──────┐ ┌────▼──────┐                             │
│  │Public      │ │Public     │                             │
│  │Subnet      │ │Subnet     │                             │
│  │us-east-1a  │ │us-east-1f │                             │
│  │            │ │           │                             │
│  │[ALB Node]  │ │[ALB Node] │                             │
│  │[EC2]       │ │           │                             │
│  └────────────┘ └───────────┘                             │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## Overview

CloudDrive is a REST API for file storage and management with advanced image processing capabilities. Users can upload multiple files simultaneously to AWS S3 (parallel multi-file uploads), organize them in folders, and share files with other users.

The backend features two Lambda functions for automatic image processing:
- **Profile photos:** Validates file types from bytes (not extensions), resizes to 400×400, prevents malicious uploads (.exe, .zip, etc.)
- **File previews:** Automatically generates 400×400 thumbnails for all uploaded images, exposed via `/image-preview/{file_id}` endpoint

I built this to learn AWS deployment, backend development, Lambda functions, event-driven architecture, and performance optimization.

## Features

### Authentication
- User registration and login
- JWT token-based authentication
- Password hashing with bcrypt
- Profile photo upload with validation

### File Management
- **Parallel multi-file uploads** - Upload multiple files simultaneously to AWS S3
- Returns presigned URLs for direct S3 uploads (bypasses backend for large files)
- Download files via presigned URLs
- Automatic preview generation for images (400×400 thumbnails)
- Replace or keep both when file conflicts occur
- Rename files
- Filter only confirmed uploads (prevents showing incomplete files)

### File Sharing
- Share files or folders with other users
- Set permissions (view or edit access)
- List shared items

### Folder Organization
- Create nested folders
- List folder contents with sorting options
- Rename folders

### Image Processing
- **Profile Photos**
  - Upload profile photos (max 5MB)
  - Lambda validates file type from bytes (prevents .exe renamed as .jpg)
  - Automatically deletes non-image files
  - Resizes valid images to 400×400
  - Performance: 512ms → 139ms (optimized)
- **File Previews**
  - Auto-generate 400×400 thumbnails for all uploaded images
  - Lambda processes uploads asynchronously (doesn't block user)
  - Performance: 6223ms → 1399ms (memory optimization)
  - Exposed via `/image-preview/{file_id}` endpoint

## Tech Stack

- **Backend:** FastAPI (Python 3.12)
- **Database:** PostgreSQL (Supabase)
- **Storage:** AWS S3
- **Compute:** AWS Lambda (image processing), AWS EC2 (API)
- **Load Balancer:** AWS Application Load Balancer
- **SSL:** AWS Certificate Manager
- **Secrets:** AWS Secrets Manager
- **Auth:** OAuth2 with JWT
- **Testing:** pytest (84% coverage)
- **Container:** Docker
- **CI/CD:** GitHub Actions
- **Deployment:** AWS EC2 behind ALB

## Project Structure
```
CloudDrive/
├── app/
│   ├── routes/          # API endpoints
│   ├── services/        # Business logic
│   ├── schemas/         # Pydantic models
│   ├── db/             # Database queries
│   └── helpers/        # Utilities
├── tests/
│   └── unit_tests/     # pytest tests
├── lambdas/
│   ├── profile_picture_validator.py
│   └── previews_and_file_confirmation.py
├── .github/workflows/  # CI/CD
├── Dockerfile
└── docker-compose.yml
```

## API Endpoints

### Authentication
- `POST /user` - Register
- `POST /login` - Login
- `GET /verify-token` - Verify JWT

### Files
- `POST /file` - Upload file (returns presigned URL)
- `GET /file/{file_id}` - Get download URL
- `PATCH /file/{file_id}` - Rename file
- `GET /image-preview/{file_id}` - Get preview URL
- `POST /confirm-file-upload` - Lambda callback (internal)
- `POST /confirm-file-preview` - Lambda callback (internal)

### Folders
- `POST /drive` - Create folder
- `GET /drive` - List root contents (filters by `confirmed_upload = TRUE`)
- `GET /drive/{folder_id}` - List folder contents
- `PATCH /drive/{folder_id}` - Rename folder

### Sharing
- `POST /share` - Share file or folder
- `GET /shared-with-me` - List shared items

### Profile
- `POST /profile-photo` - Upload profile photo
- `GET /profile-photo` - Get profile photo URL
- `POST /confirm-profile-picture` - Lambda callback (internal)

### Health
- `GET /` - API info
- `GET /health` - Health check

## Database Schema

### Key Fields
- **files table:**
  - `confirmed_upload` (BOOLEAN) - TRUE after Lambda confirms upload
  - `preview_ready` (BOOLEAN) - TRUE after Lambda generates preview
  
Backend queries filter by `confirmed_upload = TRUE` in the `/drive` endpoint to only return files that have been fully processed by Lambda.

## Getting Started

### Prerequisites
- Docker
- AWS account (S3, EC2, Lambda, IAM)
- PostgreSQL database

### Environment Variables

Create `.env`:
```env
# Database
HOST=your-db-host
PORT=5432
DATABASE=your-database
USER=your-user
PASSWORD=your-password

# AWS
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret

# Auth
SECRET_KEY=your-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Lambda
LAMBDA_SECRET=your-shared-secret

# Environment
ENVIRONMENT=local
```

### Run Locally
```bash
docker-compose up
# API available at http://localhost:8000
# Docs available at http://localhost:8000/docs
```

## Testing

```bash
# Run all tests
pytest tests/unit_tests

# With coverage
pytest --cov=app --cov-report=term-missing tests/unit_tests
```

Coverage: 84%

## Deployment

Deployed on AWS with:
- **EC2** running Docker container
- **Application Load Balancer** with:
  - SSL certificate from AWS Certificate Manager
  - CNAME record: api.clouddrive.world → ALB DNS
  - HTTPS (443) and HTTP (80) listeners
  - Health checks on `/health` endpoint
- **S3** for file storage with event triggers
- **2 Lambda Functions:**
  - ProfilePictureValidator (profile photos)
  - VerifyFilesAndCreatePreviews (file uploads + image previews)
- **Secrets Manager** for credentials
- **Multi-AZ** setup (us-east-1a, us-east-1f)

### CI/CD
GitHub Actions runs tests on every push.

### Deployment Process
1. Build Docker image
2. Push to Docker Hub
3. SSH to EC2
4. Pull latest image
5. Restart container

## Lambda Functions

### 1. ProfilePictureValidator
**Trigger:** S3 upload to `profile_photos/original/`

**Process:**
1. Downloads uploaded file
2. Checks file type from bytes (not extension)
3. If not an image → deletes from S3
4. If valid image → resizes to 400×400, uploads to `resized/`, calls backend

**Security:** Prevents users from uploading `.exe` or malicious files as profile pictures.

**Performance:** 512ms → 139ms (optimized)

### 2. VerifyFilesAndCreatePreviews
**Trigger:** S3 upload to `files/`

**Process:**
1. Parses S3 key to extract user_id and file_id
2. Confirms file upload in database (`confirmed_upload = TRUE`)
3. Checks if file is an image
4. If image:
   - Generates 400×400 thumbnail using PIL
   - Uploads to `previews/{user_id}/{file_id}`
   - Confirms preview in database (`preview_ready = TRUE`)

**Performance:** 6223ms → 1399ms (128MB → 512MB memory)

**Configuration:**
- Memory: 512MB
- Timeout: 8 seconds
- Runtime: Python 3.12

Both Lambda functions use a shared secret to authenticate with the backend API.

## What I Learned

### Backend & API Design
- FastAPI and async Python
- RESTful API design principles
- OAuth2 authentication with JWT
- Password hashing with bcrypt
- Pydantic schemas for validation
- Error handling and status codes

### AWS Services
- **EC2:** Server deployment and management
- **Application Load Balancer:** SSL termination, health checks, multi-AZ
- **S3:** Object storage, event notifications, presigned URLs, CORS configuration
- **Lambda:** Event-driven processing, performance optimization
- **Secrets Manager:** Secure credential storage
- **Certificate Manager:** SSL/TLS certificates
- **IAM:** Role-based access control

### Database
- PostgreSQL schema design
- Query optimization
- Async database operations with asyncpg
- Database migrations

### DevOps & Infrastructure
- Docker containerization
- Docker Compose for local development
- GitHub Actions CI/CD
- Multi-AZ deployment
- VPC configuration
- Security groups and network routing

### Performance Optimization
- Lambda memory tuning (128MB → 512MB)
- Image processing with PIL/Pillow
- Async/await patterns
- Database query optimization

### Testing
- pytest for unit testing
- Test fixtures and mocking
- Code coverage reporting
- CI integration

### Architecture Patterns
- Event-driven architecture with S3 triggers
- Asynchronous processing
- Shared secret authentication
- Presigned URL generation
- CORS configuration for browser access

## Future Improvements

- [ ] Search functionality
- [ ] Trash/recycle bin
- [ ] File versioning
- [ ] Batch operations
- [ ] Video preview thumbnails
- [ ] PDF preview generation
- [ ] Real-time notifications
- [ ] Rate limiting
- [ ] Caching layer (Redis)

## Contact

Built by Mauricio Moreno
- GitHub: [@mauricio0129](https://github.com/mauricio0129)
