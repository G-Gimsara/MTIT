# course-service/main.py
from fastapi import FastAPI, HTTPException, status
from models import Course, CourseCreate, CourseUpdate
from service import CourseService
from typing import List

app = FastAPI(title="Course Microservice", version="1.0.0")

# Initialize service
course_service = CourseService()

@app.get("/")
def read_root():
    return {"message": "Course Microservice is running"}

@app.get("/api/courses", response_model=List[Course])
def get_all_courses():
    """Get all courses"""
    return course_service.get_all()

@app.get("/api/courses/{course_id}", response_model=Course)
def get_course(course_id: int):
    """Get a course by ID"""
    course = course_service.get_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

@app.post("/api/courses", response_model=Course, status_code=status.HTTP_201_CREATED)
def create_course(course: CourseCreate):
    """Create a new course"""
    return course_service.create(course)

@app.put("/api/courses/{course_id}", response_model=Course)
def update_course(course_id: int, course: CourseUpdate):
    """Update a course"""
    updated_course = course_service.update(course_id, course)
    if not updated_course:
        raise HTTPException(status_code=404, detail="Course not found")
    return updated_course

@app.delete("/api/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int):
    """Delete a course"""
    success = course_service.delete(course_id)
    if not success:
        raise HTTPException(status_code=404, detail="Course not found")
    return None