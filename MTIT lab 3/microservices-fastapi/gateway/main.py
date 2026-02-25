# gateway/main.py
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import httpx
from typing import Any, Optional
import time
import logging
from datetime import datetime, timedelta

# Import authentication modules
from auth import (
    authenticate_user, create_access_token, get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES, Token, User, get_current_user
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gateway.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="API Gateway with Authentication, Logging & Error Handling",
    version="1.0.0",
    description="Complete API Gateway for Microservices Architecture"
)

# Service URLs
SERVICES = {
    "student": "http://localhost:8001",
    "course": "http://localhost:8002"
}

# ============================================
# MIDDLEWARE - Activity 3: Request Logging
# ============================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all incoming requests and responses"""
    # Generate unique request ID
    request_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{id(request)}"
    
    # Log request details
    logger.info(f"=== New Request ===")
    logger.info(f"Request ID: {request_id}")
    logger.info(f"Method: {request.method}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Client Host: {request.client.host if request.client else 'Unknown'}")
    logger.info(f"Headers: {dict(request.headers)}")
    
    # Get request body if present
    try:
        body = await request.json()
        logger.info(f"Request Body: {body}")
    except:
        logger.info("Request Body: No JSON body or unable to parse")
    
    # Process time tracking
    start_time = time.time()
    
    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response details
        logger.info(f"Response Status: {response.status_code}")
        logger.info(f"Processing Time: {process_time:.3f} seconds")
        
        # Try to log response body (if applicable)
        if response.status_code < 400:
            logger.info(f"Response: Successful")
        else:
            logger.info(f"Response: Error occurred")
        
        logger.info(f"Request ID: {request_id} - Completed")
        logger.info("=" * 50)
        
        # Add custom headers
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_id
        
        return response
        
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        logger.error(f"Request ID: {request_id} - Failed")
        logger.info("=" * 50)
        raise

# ============================================
# AUTHENTICATION ENDPOINTS - Activity 2
# ============================================
@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Get authentication token
    - username: admin / user
    - password: admin123 / user123
    """
    logger.info(f"Login attempt for user: {form_data.username}")
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    logger.info(f"Successful login for user: {form_data.username}")
    return {"access_token": access_token, "token_type": "bearer"}

# ============================================
# ENHANCED FORWARD REQUEST FUNCTION - Activity 4
# ============================================
async def forward_request(service: str, path: str, method: str, **kwargs) -> Any:
    """
    Forward request to the appropriate microservice with enhanced error handling
    """
    # Check if service exists
    if service not in SERVICES:
        error_detail = {
            "error": "Service Not Found",
            "message": f"Service '{service}' is not available",
            "available_services": list(SERVICES.keys()),
            "timestamp": datetime.now().isoformat(),
            "status_code": 404
        }
        logger.error(f"Service not found: {service}")
        raise HTTPException(status_code=404, detail=error_detail)
    
    # Construct URL
    url = f"{SERVICES[service]}{path}"
    logger.info(f"Forwarding {method} request to: {url}")
    
    # Make request with timeout
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Handle different HTTP methods
            if method == "GET":
                response = await client.get(url, **kwargs)
            elif method == "POST":
                response = await client.post(url, **kwargs)
            elif method == "PUT":
                response = await client.put(url, **kwargs)
            elif method == "DELETE":
                response = await client.delete(url, **kwargs)
            else:
                error_detail = {
                    "error": "Method Not Allowed",
                    "message": f"HTTP method '{method}' is not supported",
                    "allowed_methods": ["GET", "POST", "PUT", "DELETE"],
                    "timestamp": datetime.now().isoformat(),
                    "status_code": 405
                }
                logger.error(f"Method not allowed: {method}")
                raise HTTPException(status_code=405, detail=error_detail)
            
            # Handle service error responses (4xx, 5xx)
            if response.status_code >= 400:
                try:
                    error_content = response.json() if response.text else {}
                except:
                    error_content = {"detail": response.text}
                
                error_detail = {
                    "error": "Service Error",
                    "message": error_content.get("detail", "Unknown error from service"),
                    "service": service,
                    "service_url": url,
                    "service_status_code": response.status_code,
                    "timestamp": datetime.now().isoformat(),
                    "status_code": response.status_code
                }
                logger.error(f"Service error from {service}: {response.status_code}")
                return JSONResponse(
                    content=error_detail,
                    status_code=response.status_code
                )
            
            # Successful response
            logger.info(f"Successful response from {service}: {response.status_code}")
            return JSONResponse(
                content=response.json() if response.text else {"message": "Success"},
                status_code=response.status_code
            )
            
        # Enhanced error handling for various exceptions
        except httpx.TimeoutException:
            error_detail = {
                "error": "Service Timeout",
                "message": f"The {service} service did not respond in time",
                "service": service,
                "service_url": url,
                "timeout_seconds": 10,
                "timestamp": datetime.now().isoformat(),
                "status_code": 504
            }
            logger.error(f"Timeout error for {service}: {url}")
            raise HTTPException(status_code=504, detail=error_detail)
            
        except httpx.ConnectionError:
            error_detail = {
                "error": "Connection Error",
                "message": f"Could not connect to {service} service. Make sure it's running on {SERVICES[service]}",
                "service": service,
                "service_url": url,
                "expected_url": SERVICES[service],
                "timestamp": datetime.now().isoformat(),
                "status_code": 503
            }
            logger.error(f"Connection error for {service}: {url}")
            raise HTTPException(status_code=503, detail=error_detail)
            
        except httpx.HTTPError as e:
            error_detail = {
                "error": "HTTP Error",
                "message": f"HTTP error occurred: {str(e)}",
                "service": service,
                "service_url": url,
                "timestamp": datetime.now().isoformat(),
                "status_code": 502
            }
            logger.error(f"HTTP error for {service}: {str(e)}")
            raise HTTPException(status_code=502, detail=error_detail)
            
        except Exception as e:
            error_detail = {
                "error": "Internal Server Error",
                "message": f"An unexpected error occurred: {str(e)}",
                "service": service,
                "service_url": url,
                "timestamp": datetime.now().isoformat(),
                "status_code": 500
            }
            logger.error(f"Unexpected error for {service}: {str(e)}")
            raise HTTPException(status_code=500, detail=error_detail)

# ============================================
# ROOT ENDPOINT
# ============================================
@app.get("/")
async def read_root():
    """Gateway root endpoint with service information"""
    return {
        "message": "API Gateway is running",
        "version": "1.0.0",
        "available_services": list(SERVICES.keys()),
        "endpoints": {
            "authentication": "/token",
            "health_check": "/health",
            "logs": "/logs",
            "student_service": "/gateway/students",
            "course_service": "/gateway/courses"
        },
        "timestamp": datetime.now().isoformat()
    }

# ============================================
# HEALTH CHECK ENDPOINT - Activity 4
# ============================================
@app.get("/health")
async def health_check():
    """Check health of all services"""
    health_status = {
        "gateway": {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        },
        "services": {}
    }
    
    for service_name, service_url in SERVICES.items():
        try:
            async with httpx.AsyncClient() as client:
                start_time = time.time()
                response = await client.get(f"{service_url}/", timeout=5.0)
                response_time = time.time() - start_time
                
                health_status["services"][service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "url": service_url,
                    "response_code": response.status_code,
                    "response_time": f"{response_time:.3f}s",
                    "message": "Service is responding"
                }
        except httpx.TimeoutException:
            health_status["services"][service_name] = {
                "status": "unhealthy",
                "url": service_url,
                "error": "Timeout - Service not responding",
                "message": "Service timeout after 5 seconds"
            }
        except httpx.ConnectionError:
            health_status["services"][service_name] = {
                "status": "unhealthy",
                "url": service_url,
                "error": "Connection refused",
                "message": "Service is not running or port is closed"
            }
        except Exception as e:
            health_status["services"][service_name] = {
                "status": "unhealthy",
                "url": service_url,
                "error": str(e),
                "message": "Unexpected error"
            }
    
    # Determine overall status
    all_healthy = all(s["status"] == "healthy" for s in health_status["services"].values())
    health_status["overall_status"] = "healthy" if all_healthy else "degraded"
    
    return health_status

# ============================================
# LOGS ENDPOINT - Activity 3
# ============================================
@app.get("/logs")
async def get_logs(lines: int = 50, current_user = Depends(get_current_active_user)):
    """
    View recent logs (protected endpoint)
    - Requires authentication
    - Default shows last 50 lines
    """
    try:
        with open('gateway.log', 'r') as f:
            log_lines = f.readlines()[-lines:]
            return {
                "status": "success",
                "lines_requested": lines,
                "lines_returned": len(log_lines),
                "logs": log_lines,
                "timestamp": datetime.now().isoformat()
            }
    except FileNotFoundError:
        return {
            "status": "warning",
            "message": "No log file found",
            "logs": ["Log file not created yet. Make some requests first."]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error reading logs: {str(e)}",
            "logs": []
        }

# ============================================
# STUDENT SERVICE ROUTES (Protected)
# ============================================
@app.get("/gateway/students")
async def get_all_students(current_user = Depends(get_current_active_user)):
    """Get all students (Authentication Required)"""
    logger.info(f"User {current_user['username']} requested all students")
    return await forward_request("student", "/api/students", "GET")

@app.get("/gateway/students/{student_id}")
async def get_student(student_id: int, current_user = Depends(get_current_active_user)):
    """Get a student by ID (Authentication Required)"""
    logger.info(f"User {current_user['username']} requested student ID: {student_id}")
    return await forward_request("student", f"/api/students/{student_id}", "GET")

@app.post("/gateway/students")
async def create_student(request: Request, current_user = Depends(get_current_active_user)):
    """Create a new student (Authentication Required)"""
    body = await request.json()
    logger.info(f"User {current_user['username']} creating new student: {body.get('name', 'Unknown')}")
    return await forward_request("student", "/api/students", "POST", json=body)

@app.put("/gateway/students/{student_id}")
async def update_student(student_id: int, request: Request, current_user = Depends(get_current_active_user)):
    """Update a student (Authentication Required)"""
    body = await request.json()
    logger.info(f"User {current_user['username']} updating student ID: {student_id}")
    return await forward_request("student", f"/api/students/{student_id}", "PUT", json=body)

@app.delete("/gateway/students/{student_id}")
async def delete_student(student_id: int, current_user = Depends(get_current_active_user)):
    """Delete a student (Authentication Required)"""
    logger.info(f"User {current_user['username']} deleting student ID: {student_id}")
    return await forward_request("student", f"/api/students/{student_id}", "DELETE")

# ============================================
# COURSE SERVICE ROUTES (Protected) - Activity 1
# ============================================
@app.get("/gateway/courses")
async def get_all_courses(current_user = Depends(get_current_active_user)):
    """Get all courses (Authentication Required)"""
    logger.info(f"User {current_user['username']} requested all courses")
    return await forward_request("course", "/api/courses", "GET")

@app.get("/gateway/courses/{course_id}")
async def get_course(course_id: int, current_user = Depends(get_current_active_user)):
    """Get a course by ID (Authentication Required)"""
    logger.info(f"User {current_user['username']} requested course ID: {course_id}")
    return await forward_request("course", f"/api/courses/{course_id}", "GET")

@app.post("/gateway/courses")
async def create_course(request: Request, current_user = Depends(get_current_active_user)):
    """Create a new course (Authentication Required)"""
    body = await request.json()
    logger.info(f"User {current_user['username']} creating new course: {body.get('name', 'Unknown')}")
    return await forward_request("course", "/api/courses", "POST", json=body)

@app.put("/gateway/courses/{course_id}")
async def update_course(course_id: int, request: Request, current_user = Depends(get_current_active_user)):
    """Update a course (Authentication Required)"""
    body = await request.json()
    logger.info(f"User {current_user['username']} updating course ID: {course_id}")
    return await forward_request("course", f"/api/courses/{course_id}", "PUT", json=body)

@app.delete("/gateway/courses/{course_id}")
async def delete_course(course_id: int, current_user = Depends(get_current_active_user)):
    """Delete a course (Authentication Required)"""
    logger.info(f"User {current_user['username']} deleting course ID: {course_id}")
    return await forward_request("course", f"/api/courses/{course_id}", "DELETE")

# ============================================
# ERROR HANDLERS - Activity 4
# ============================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom handler for HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Exception",
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Custom handler for general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred",
            "path": request.url.path,
            "method": request.method,
            "timestamp": datetime.now().isoformat()
        }
    )

# ============================================
# ADDITIONAL UTILITY ENDPOINTS
# ============================================
@app.get("/gateway/services")
async def list_services(current_user = Depends(get_current_active_user)):
    """List all available services (Authentication Required)"""
    return {
        "services": SERVICES,
        "count": len(SERVICES),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/gateway/service/{service_name}/status")
async def service_status(service_name: str, current_user = Depends(get_current_active_user)):
    """Check status of a specific service (Authentication Required)"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SERVICES[service_name]}/", timeout=5.0)
            return {
                "service": service_name,
                "url": SERVICES[service_name],
                "status": "online" if response.status_code == 200 else "degraded",
                "response_code": response.status_code,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "service": service_name,
            "url": SERVICES[service_name],
            "status": "offline",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }