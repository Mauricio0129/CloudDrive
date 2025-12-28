# CloudDrive

A file storage API built with FastAPI, PostgreSQL, and AWS S3. Supports user authentication, file management, and granular sharing permissions.

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
│ - SSL/TLS Termination (HTTPS → HTTP)        │
│ - Health Check: /health                     │
│ - Listener: 80, 443                         │
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
       │         │ 3. Detect REAL file type (bytes)     │
       │         │                                      │
       │         │ IF NOT IMAGE (.exe, .zip, etc):      │
       │         │   ✗ Delete from S3                   │
       │         │   ✗ Exit (no /confirm call)          │
       │         │                                      │
       │         │ IF IS IMAGE (JPEG/PNG/GIF/WebP):     │
       │         │   ✓ Resize to 400x400                │
       │         │   ✓ Detect true extension            │
       │         │   ✓ Re-upload to resized/ with       │
       │         │     correct extension (photo.png)    │
       │         │   ✓ Delete original                  │
       │         │   ✓ Call /confirm-profile-picture    │
       │         │     Headers:                         │
       │         │       X-Lambda-Secret: {hex_32_str}  │
       │         │     Body:                            │
       │         │       {user_id, extension}           │
       │         │                                      │
       │         │ Performance: 512ms → 139ms           │
       │         │ (Optimized via GB-second pricing)    │
       │         └────────────┬─────────────────────────┘
       │                      │
       │                      │ Uploads resized image
       │                      ↓
       │              (Back to S3: resized/)
       │                      │
       │                      │ POST /confirm-profile-picture
       │                      │ (Calls back to EC2 via ALB)
       │                      ↓
       │              ┌───────────────────────┐
       │              │ Backend Validates:    │
       │              │ - X-Lambda-Secret     │
       │              │                       │
       │              │ Updates Supabase:     │
       │              │ - has_profile_picture │
       │              │   = true              │
       │              │ - profile_pic_ext     │
       │              │   = detected ext      │
       │              └───────────────────────┘
       │
       │ Uses for encryption
       ↓
┌─────────────┐
│  AWS KMS    │
│             │
│ aws/secrets │
│ manager_key │
│             │
│ Encrypts    │
│ secrets at  │
│ rest        │
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

Security Features:
──────────────────
✓ SSL/TLS termination at ALB (HTTPS)
✓ IAM roles with least-privilege access
✓ Secrets Manager for credentials (no hardcoded values)
✓ KMS encryption for secrets at rest
✓ Security Groups restricting traffic
✓ Lambda serverless validation (defense in depth)
✓ File type detection from bytes (don't trust extensions)
✓ Automatic malicious file deletion
✓ Lambda webhook authentication (X-Lambda-Secret)
✓ CORS configured on S3 for browser security
```

CloudDrive uses a production-grade AWS architecture with:
- **Application Load Balancer** for traffic distribution, SSL/TLS termination, and health checks
- **EC2 (Ubuntu)** running Dockerized FastAPI application with port mapping (80:8080)
- **S3** for scalable file storage with event-driven triggers
- **Lambda** for serverless image validation, resizing (400x400), and security enforcement
- **Supabase PostgreSQL** for relational data (users, files, folders, shares)
- **AWS Secrets Manager** for secure credential management with KMS encryption
- **Multi-AZ deployment** across us-east-1a and us-east-1f for high availability
- **IAM roles** with least-privilege access policies (S3, Secrets Manager)
- **VPC networking** with Internet Gateway, Route Tables, and Security Groups
- **Defense-in-depth security** with Lambda validation layer preventing malicious uploads

## Overview

CloudDrive is a REST API that handles file storage and management. Users can upload files to AWS S3, organize them in folders, and share files with specific permissions (view or edit access).

I built this project to learn:
- Deploying applications to AWS (EC2, Load Balancer, S3, Secrets Manager)
- Structuring backend services in the cloud
- OAuth2 authentication with JWT tokens
- Docker containerization and deployment
- PostgreSQL database design
- Automated testing with pytest
- CI/CD pipelines with GitHub Actions

## Key Achievements

- **Optimized Lambda image processing performance from 512ms to 139ms** (73% improvement) by analyzing AWS GB-second pricing and choosing cost-effective memory allocation
- **Implemented serverless security validation** - Lambda functions automatically validate and delete non-image files uploaded as profile pictures, preventing malicious file uploads (.exe, .zip, etc.)
- **Achieved 84% test coverage** with comprehensive unit and integration tests using pytest and asyncio
- **Deployed production infrastructure across 2 availability zones** with automated health checks and Application Load Balancer
- **Implemented granular file sharing permissions** with view/edit access control and ownership validation
- **Secured application traffic with HTTPS** using SSL/TLS certificates through AWS Certificate Manager on the Application Load Balancer

## Features

### Authentication
- User registration and login
- JWT token-based authentication
- Token verification endpoint
- Password hashing with bcrypt

### File Management
- Upload files to AWS S3 with presigned URLs
- Download files with temporary access URLs
- Replace existing files (conflict handling)
- Keep both files option when conflicts occur
- Rename files
- File ownership validation

### File Sharing
- Share files with other users
- Share entire folders with other users
- Granular permissions (view-only or edit access)
- List all files/folders shared with you

### Folder Organization
- Create nested folder structures
- List folder contents with sorting (by name/date, asc/desc)
- Rename folders
- Folder ownership validation

### Profile Management
- Upload profile photos with size validation (max 5MB)
- **Automated file type validation via Lambda** - ensures only valid image formats (JPEG, PNG, GIF, WebP) are accepted
- **Automatic malicious file deletion** - Lambda automatically deletes non-image files (e.g., .exe, .zip) from S3 before they can be used
- Download profile photos with presigned URLs
- Secure Lambda webhook with secret validation

## Tech Stack

- **Backend Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL (hosted on Supabase)
- **File Storage:** AWS S3
- **Serverless Compute:** AWS Lambda (for image validation and processing)
- **Secrets Management:** AWS Secrets Manager
- **Authentication:** OAuth2 with JWT tokens
- **Testing:** pytest with 84% code coverage
- **Containerization:** Docker
- **CI/CD:** GitHub Actions
- **Deployment:** AWS EC2 behind Application Load Balancer

## Project Structure
```
CloudDrive/
├── app/
│   ├── routes/          # API endpoints
│   ├── services/        # Business logic
│   ├── schemas/         # Pydantic models
│   ├── db/             # Database queries
│   └── helpers/        # Utility functions
├── tests/
│   └── unit_tests/     # pytest test suite
├── .github/workflows/  # CI/CD pipeline
├── Dockerfile          # Container configuration
└── docker-compose.yml  # Local development setup
```

## API Endpoints

### Authentication
- `POST /user` - Create new user account
- `POST /login` - Login and receive JWT token
- `GET /verify-token` - Validate JWT token

### Files
- `POST /file` - Upload file (with conflict handling: replace/keep both)
- `GET /file/{file_id}` - Get download URL for file
- `PATCH /file/{file_id}` - Rename file

### Folders
- `POST /drive` - Create new folder
- `GET /drive` - List root folder contents
- `GET /drive/{folder_id}` - List folder contents (with sorting)
- `PATCH /drive/{folder_id}` - Rename folder

### Sharing
- `POST /share` - Share file or folder with another user
- `GET /shared-with-me` - List all files/folders shared with you

### Profile
- `POST /profile-photo` - Upload profile photo (generates presigned S3 upload URL)
- `GET /profile-photo` - Get profile photo download URL
- `POST /confirm-profile-picture` - Lambda callback endpoint for profile picture validation (internal)

### Health
- `GET /` - API welcome message
- `GET /health` - Health check endpoint

## Getting Started

### Prerequisites
- Docker
- AWS account with:
  - S3 bucket created
  - IAM credentials (access key + secret key)
- PostgreSQL database (Supabase or self-hosted)

### Environment Variables

Create a `.env` file in the project root:
```env
# Database
HOST=your-db-host
PORT=5432
DATABASE=your-database-name
USER=your-db-user
PASSWORD=your-db-password

# AWS
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Authentication
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Environment
ENVIRONMENT=local
```

### Running Locally
```bash
# Start the application
docker-compose up

# The API will be available at http://localhost:8000
```

## Testing

The project includes unit tests with 84% code coverage.

### Run tests locally
```bash
# Run all tests
pytest tests/unit_tests

# Run with coverage report
pytest --cov=app --cov-report=term-missing tests/unit_tests
```

### Run tests in Docker
```bash
docker-compose run --rm backend pytest tests/unit_tests
```

### What's tested
- File upload/download/replace/rename operations
- Folder creation, renaming, and content retrieval
- User registration and authentication
- File and folder sharing with permissions
- Error handling and edge cases

## Deployment

CloudDrive is deployed on AWS with production-grade infrastructure.

### Why AWS instead of Vercel/Netlify?

I wanted to learn real cloud infrastructure - not just platform-as-a-service deployment. This meant understanding load balancers, security groups, IAM policies, VPC networking, and managing compute resources directly. While PaaS solutions are great for quick deployments, building on raw AWS teaches the fundamentals of how modern cloud systems actually work.

### AWS Infrastructure

- **EC2 Instance** - Runs the Docker container with the FastAPI application
- **Application Load Balancer** - Routes traffic and performs health checks on `/health` endpoint
- **S3** - Stores all uploaded files and profile photos
- **Secrets Manager** - Manages database credentials and API keys securely
- **Security Groups** - Controls inbound/outbound traffic to EC2 instance
- **VPC** - Multi-AZ deployment with Internet Gateway and Route Tables

### CI/CD Pipeline

GitHub Actions automatically:
- Runs all tests on every push
- Validates code coverage
- Ensures all checks pass before deployment

### Deployment Process

1. Build Docker image locally with production environment
2. Push image to Docker Hub
3. SSH into EC2 instance
4. Pull latest image from Docker Hub
5. Stop existing container and start new one with updated image
6. Load balancer health checks verify deployment

### Production Environment Variables

Production uses AWS Secrets Manager for sensitive credentials instead of `.env` files.

## Lambda Security Validation

CloudDrive implements a serverless security layer to prevent malicious file uploads:

### Profile Picture Upload Flow

1. **User requests upload URL** - FastAPI generates presigned S3 upload URL with 5MB size limit
2. **User uploads file to S3** - File is uploaded directly to `profile_photos/original/{user_id}/photo`
3. **S3 triggers Lambda function** - Automatic event trigger on new file upload to `original/` folder
4. **Lambda downloads and validates** - Downloads file and detects REAL file type by reading file bytes (magic numbers)
5. **Lambda takes action:**
   - ❌ **Invalid file (e.g., .exe, .zip, .pdf):** Automatically deletes from S3, exits without calling backend
   - ✅ **Valid image (JPEG, PNG, GIF, WebP):**
     - Resizes image to 400x400 pixels
     - Detects true file extension from bytes
     - Re-uploads to `profile_photos/resized/{user_id}/photo.{ext}` with correct extension
     - Deletes original file from S3
     - Calls `/confirm-profile-picture` endpoint with:
       - Header: `X-Lambda-Secret: {hex_32_char_string}` for authentication
       - Body: `{user_id, extension}`
6. **Backend confirms upload:**
   - Validates Lambda secret
   - Updates database: `has_profile_picture = true`, `profile_pic_ext = detected_extension`
7. **Future requests** - When users request profile pictures, backend generates presigned download URL for `photo.{ext}` using stored extension

### Why This Matters

**Client-side validation isn't enough.** An attacker can:
- Bypass frontend checks entirely
- Upload malicious files directly to S3 using the presigned URL
- Rename `.exe` files to `.jpg` to fool basic extension checks

The Lambda validation layer ensures:
- **File type detection from bytes** - Can't be fooled by renaming files
- **Automatic threat deletion** - Malicious files never reach users
- **Extension correction** - Files are re-uploaded with correct extensions based on actual content
- **Zero-trust approach** - Validate server-side, never trust client input
- **Database integrity** - Only confirmed, validated images are tracked in the database

This pattern demonstrates **defense in depth** - even if someone bypasses the frontend and forges file extensions, the serverless validation layer automatically detects and removes threats before they can be accessed.

## What I Learned

- **AWS Deployment:** Setting up EC2 instances, configuring load balancers, managing S3 buckets, and using Secrets Manager
- **Serverless Architecture:** Building event-driven Lambda functions triggered by S3 uploads, implementing webhook security with secrets, and optimizing Lambda performance/cost
- **FastAPI:** Building REST APIs with dependency injection, async/await patterns, and OAuth2 authentication
- **Docker:** Creating multi-stage builds, container networking, volume mounting, and understanding host-gateway configuration
- **PostgreSQL:** Designing database schemas with foreign keys, constraints, and handling unique violations
- **Testing:** Writing async tests with pytest, creating fixtures, mocking external services (S3, database), and achieving 84% coverage
- **CI/CD:** Setting up GitHub Actions for automated testing on every push
- **Authentication:** Implementing OAuth2 flow with JWT tokens, password hashing with bcrypt
- **Cloud Architecture:** Understanding how to structure backend services in the cloud with load balancers, storage, and compute
- **Performance Optimization:** Profiling Lambda functions and optimizing based on AWS pricing models to reduce costs while improving performance
- **Security:** Implementing defense-in-depth with serverless validation layers, preventing malicious file uploads, and securing webhooks
