# CloudDrive

A file storage API built with FastAPI, PostgreSQL, and AWS S3. Supports user authentication, file management, and granular sharing permissions.

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
- Upload profile photos
- Download profile photos with presigned URLs

## Tech Stack

- **Backend Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL (hosted on Supabase)
- **File Storage:** AWS S3
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
- `POST /profile_photo` - Upload profile photo
- `GET /profile_photo` - Get profile photo download URL

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

CloudDrive is deployed on AWS with the following architecture:

### AWS Infrastructure

- **EC2 Instance** - Runs the Docker container with the FastAPI application
- **Application Load Balancer** - Routes traffic and performs health checks on `/health` endpoint
- **S3** - Stores all uploaded files and profile photos
- **Secrets Manager** - Manages database credentials and API keys securely
- **Security Groups** - Controls inbound/outbound traffic to EC2 instance

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

## What I Learned

- **AWS Deployment:** Setting up EC2 instances, configuring load balancers, managing S3 buckets, and using Secrets Manager
- **FastAPI:** Building REST APIs with dependency injection, async/await patterns, and OAuth2 authentication
- **Docker:** Creating multi-stage builds, container networking, volume mounting, and understanding host-gateway configuration
- **PostgreSQL:** Designing database schemas with foreign keys, constraints, and handling unique violations
- **Testing:** Writing async tests with pytest, creating fixtures, mocking external services (S3, database), and achieving 84% coverage
- **CI/CD:** Setting up GitHub Actions for automated testing on every push
- **Authentication:** Implementing OAuth2 flow with JWT tokens, password hashing with bcrypt
- **Cloud Architecture:** Understanding how to structure backend services in the cloud with load balancers, storage, and compute
