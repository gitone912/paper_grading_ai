from django.db import models
import uuid

class Subject(models.Model):
    """Different subjects for grading"""
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class MarkingScheme(models.Model):
    """Reusable marking schemes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    user_id = models.CharField(max_length=50)  # Reference to user service
    criteria = models.JSONField()  # Store marking criteria as JSON
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.subject.name}"

class QuestionPaper(models.Model):
    """Uploaded question papers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    marking_scheme = models.ForeignKey(MarkingScheme, on_delete=models.CASCADE)
    uploaded_by = models.CharField(max_length=50)  # Reference to user service
    
    # File and extracted content
    paper_file = models.FileField(upload_to='papers/')
    extracted_questions = models.JSONField(default=list)  # Store questions as JSON
    total_marks = models.PositiveIntegerField(default=0)
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class StudentSubmission(models.Model):
    """Student answer submissions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question_paper = models.ForeignKey(QuestionPaper, on_delete=models.CASCADE)
    student_name = models.CharField(max_length=200)
    student_id = models.CharField(max_length=50, blank=True)
    
    # Answer sheet
    answer_file = models.FileField(upload_to='answers/')
    extracted_answers = models.JSONField(default=list)  # Store answers as JSON
    
    # Grading results
    is_graded = models.BooleanField(default=False)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    detailed_results = models.JSONField(default=dict)  # Store detailed grading
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.student_name} - {self.question_paper.title}"

class GradingSession(models.Model):
    """Track grading sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question_paper = models.ForeignKey(QuestionPaper, on_delete=models.CASCADE)
    initiated_by = models.CharField(max_length=50)  # Reference to user service
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    total_submissions = models.PositiveIntegerField(default=0)
    processed_submissions = models.PositiveIntegerField(default=0)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Session - {self.question_paper.title}"