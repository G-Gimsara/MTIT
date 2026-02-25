# course-service/data_service.py
from models import Course

class CourseMockDataService:
    def __init__(self):
        self.courses = [
            Course(id=1, name="Python Programming", code="CS101", credits=3, 
                   instructor="Dr. Smith", department="Computer Science"),
            Course(id=2, name="Database Systems", code="CS201", credits=4, 
                   instructor="Prof. Johnson", department="Information Technology"),
            Course(id=3, name="Web Development", code="CS301", credits=3, 
                   instructor="Dr. Williams", department="Software Engineering"),
        ]
        self.next_id = 4

    def get_all_courses(self):
        return self.courses

    def get_course_by_id(self, course_id: int):
        return next((c for c in self.courses if c.id == course_id), None)

    def add_course(self, course_data):
        new_course = Course(id=self.next_id, **course_data.dict())
        self.courses.append(new_course)
        self.next_id += 1
        return new_course

    def update_course(self, course_id: int, course_data):
        course = self.get_course_by_id(course_id)
        if course:
            update_data = course_data.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(course, key, value)
            return course
        return None

    def delete_course(self, course_id: int):
        course = self.get_course_by_id(course_id)
        if course:
            self.courses.remove(course)
            return True
        return False