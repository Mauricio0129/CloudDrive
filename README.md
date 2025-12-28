# CloudDrive

A file storage API built with FastAPI, PostgreSQL, and AWS S3. Supports user authentication, file management, and file sharing with permissions.

## Architecture

```
┌─────────────┐
│ User/Browser│
└──────┬──────┘
       │
       │ HTTP (Port 80) or HTTPS (Port 443)
       ↓
┌──────────────────────────────────────────────┐
│ Application Load Balancer                    │
│ CloudDriveBackendLoadBalancer                │
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
       │                │ └── user_files/{user_id}/...
       │                │
       │                │ S3 Event Trigger
       │                │ (on upload to profile_photos/original/*)
       │                ↓
       │         ┌──────────────────────────────────────┐
       │         │ AWS Lambda                           │
       │         │ ProfilePictureValidator              │
       │         │                                      │
       │         │ Trigger: S3 PUT to original/         │
       │         │                                      │
       │         │ Process:                             │
       │         │ 1. Get key from S3 event             │
       │         │ 2. Download file                     │
       │         │ 3. Detect file type from bytes       │
       │         │                                      │
       │         │ IF NOT IMAGE (.exe, .zip, etc):      │
       │         │   - Delete from S3                   │
       │         │   - Exit                             │
       │         │                                      │
       │         │ IF IS IMAGE (JPEG/PNG/GIF/WebP):     │
       │         │   - Resize to 400x400                │
       │         │   - Detect actual extension          │
       │         │   - Upload to resized/ folder        │
       │         │   - Delete original                  │
       │         │   - Call /confirm-profile-picture    │
       │         │     with shared secret               │
       │         │                                      │
       │         │ Performance: 512ms → 139ms           │
       │         │ (optimized memory allocation)        │
       │         └────────────┬─────────────────────────┘
       │                      │
       │                      │ Uploads resized image
       │                      ↓
       │              (Back to S3: resized/)
       │                      │
       │                      │ POST /confirm-profile-picture
       │                      │ Header: X-Lambda-Secret: {hex_32}
       │                      ↓
       │              ┌───────────────────────┐
       │              │ Backend:              │
       │              │ - Verify shared secret│
       │              │ - Update database     │
       │              │   has_profile_picture │
       │              │   = true              │
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

CloudDrive is a REST API for file storage and management. Users can upload files to AWS S3, organize them in folders, and share files with other users.

I built this to learn AWS deployment, backend development, and cloud architecture.

## Features

### Authentication
- User registration and login
- JWT token-based authentication
- Password hashing with bcrypt

### File Management
- Upload files to AWS S3
- Download files via presigned URLs
- Replace or keep both when file conflicts occur
- Rename files

### File Sharing
- Share files or folders with other users
- Set permissions (view or edit access)
- List shared items

### Folder Organization
- Create nested folders
- List folder contents with sorting options
- Rename folders

### Profile Photos
- Upload profile photos (max 5MB)
- Automatic image validation via Lambda
- Image resizing to 400x400

## Tech Stack

- **Backend:** FastAPI (Python 3.12)
- **Database:** PostgreSQL (Supabase)
- **Storage:** AWS S3
- **Compute:** AWS Lambda (image processing), AWS EC2 (API)
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
- `POST /file` - Upload file
- `GET /file/{file_id}` - Get download URL
- `PATCH /file/{file_id}` - Rename file

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
- `POST /confirm-profile-picture` - Lambda callback (internal)

### Health
- `GET /` - API info
- `GET /health` - Health check

## Getting Started

### Prerequisites
- Docker
- AWS account (S3, EC2, IAM)
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

# Environment
ENVIRONMENT=local
```

### Run Locally
```bash
docker-compose up
# API available at http://localhost:8000
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
- EC2 running Docker container
- Application Load Balancer with:
  - SSL certificate from AWS Certificate Manager
  - CNAME record pointing domain to ALB
  - HTTPS (443) and HTTP (80) listeners
  - Health checks on `/health` endpoint
- S3 for file storage
- Lambda for image processing
- Secrets Manager for credentials
- Multi-AZ setup (us-east-1a, us-east-1f)

### CI/CD
GitHub Actions runs tests on every push.

### Deployment Process
1. Build Docker image
2. Push to Docker Hub
3. SSH to EC2
4. Pull latest image
5. Restart container

## Lambda Image Processing

When users upload profile photos:

1. File uploads to S3 `profile_photos/original/{user_id}/photo`
2. S3 triggers Lambda function
3. Lambda:
   - Downloads file
   - Checks file type from bytes (not extension)
   - If not an image → deletes from S3
   - If valid image → resizes to 400x400, uploads to `resized/` folder, calls backend
4. Backend verifies Lambda's shared secret, updates database

This prevents users from uploading `.exe` or other malicious files as profile pictures.

## What I Learned

- AWS deployment (EC2, ALB, S3, Secrets Manager, Lambda, Certificate Manager)
- SSL/TLS certificate setup and DNS configuration
- FastAPI and async Python
- Docker containerization
- PostgreSQL database design
- OAuth2 authentication with JWT
- Testing with pytest
- CI/CD with GitHub Actions
- S3 event-driven architecture
- Image processing optimization
