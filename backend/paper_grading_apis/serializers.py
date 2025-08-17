# serializers.py
from rest_framework import serializers
from .models import Subject, MarkingScheme, QuestionPaper, StudentSubmission, GradingSession

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['created_at']

class MarkingSchemeSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    
    class Meta:
        model = MarkingScheme
        fields = [
            'id', 'name', 'subject', 'subject_name', 'user_id', 
            'criteria', 'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']

class QuestionPaperSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    marking_scheme_name = serializers.CharField(source='marking_scheme.name', read_only=True)
    questions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = QuestionPaper
        fields = [
            'id', 'title', 'subject', 'subject_name', 'marking_scheme', 
            'marking_scheme_name', 'uploaded_by', 'paper_file', 
            'extracted_questions', 'total_marks', 'is_processed', 
            'created_at', 'questions_count'
        ]
        read_only_fields = ['extracted_questions', 'is_processed', 'created_at']
    
    def get_questions_count(self, obj):
        return len(obj.extracted_questions) if obj.extracted_questions else 0

class StudentSubmissionSerializer(serializers.ModelSerializer):
    question_paper_title = serializers.CharField(source='question_paper.title', read_only=True)
    
    class Meta:
        model = StudentSubmission
        fields = [
            'id', 'question_paper', 'question_paper_title', 'student_name', 
            'student_id', 'answer_file', 'extracted_answers', 'is_graded', 
            'total_marks', 'percentage', 'detailed_results', 'submitted_at', 
            'graded_at'
        ]
        read_only_fields = [
            'extracted_answers', 'is_graded', 'total_marks', 'percentage', 
            'detailed_results', 'submitted_at', 'graded_at'
        ]

class GradingSessionSerializer(serializers.ModelSerializer):
    question_paper_title = serializers.CharField(source='question_paper.title', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = GradingSession
        fields = [
            'id', 'question_paper', 'question_paper_title', 'initiated_by', 
            'status', 'total_submissions', 'processed_submissions', 
            'started_at', 'completed_at', 'progress_percentage'
        ]
        read_only_fields = [
            'total_submissions', 'processed_submissions', 'started_at', 
            'completed_at'
        ]
    
    def get_progress_percentage(self, obj):
        if obj.total_submissions > 0:
            return (obj.processed_submissions / obj.total_submissions) * 100
        return 0