# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubjectViewSet, MarkingSchemeViewSet, QuestionPaperViewSet, 
    StudentSubmissionViewSet, GradingSessionViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'subjects', SubjectViewSet)
router.register(r'marking-schemes', MarkingSchemeViewSet)
router.register(r'question-papers', QuestionPaperViewSet)
router.register(r'submissions', StudentSubmissionViewSet)
router.register(r'grading-sessions', GradingSessionViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]

# Generated API endpoints:
"""
Subjects:
- GET    /api/subjects/                     - List all subjects
- POST   /api/subjects/                     - Create new subject
- GET    /api/subjects/{id}/                - Get subject details
- PUT    /api/subjects/{id}/                - Update subject
- DELETE /api/subjects/{id}/                - Delete subject

Marking Schemes:
- GET    /api/marking-schemes/              - List marking schemes
- POST   /api/marking-schemes/              - Create marking scheme
- GET    /api/marking-schemes/{id}/         - Get marking scheme details
- PUT    /api/marking-schemes/{id}/         - Update marking scheme
- DELETE /api/marking-schemes/{id}/         - Delete marking scheme
- POST   /api/marking-schemes/{id}/deactivate/ - Deactivate scheme

Question Papers:
- GET    /api/question-papers/              - List question papers
- POST   /api/question-papers/              - Upload question paper
- GET    /api/question-papers/{id}/         - Get paper details
- PUT    /api/question-papers/{id}/         - Update paper
- DELETE /api/question-papers/{id}/         - Delete paper
- POST   /api/question-papers/{id}/process-paper/ - Process paper
- GET    /api/question-papers/{id}/questions/ - Get extracted questions

Student Submissions:
- GET    /api/submissions/                  - List submissions
- POST   /api/submissions/                  - Upload submission
- GET    /api/submissions/{id}/             - Get submission details
- PUT    /api/submissions/{id}/             - Update submission
- DELETE /api/submissions/{id}/             - Delete submission
- POST   /api/submissions/{id}/grade-submission/ - Grade submission
- GET    /api/submissions/{id}/results/     - Get grading results

Grading Sessions:
- GET    /api/grading-sessions/             - List grading sessions
- POST   /api/grading-sessions/             - Create session
- GET    /api/grading-sessions/{id}/        - Get session details
- PUT    /api/grading-sessions/{id}/        - Update session
- DELETE /api/grading-sessions/{id}/        - Delete session
- POST   /api/grading-sessions/{id}/start-grading/ - Start batch grading
- GET    /api/grading-sessions/{id}/status-check/ - Check session status

Query Parameters:
- subjects: ?search=math
- marking-schemes: ?user_id=123&subject_id=1&is_active=true
- question-papers: ?uploaded_by=123&subject_id=1&is_processed=true
- submissions: ?question_paper_id=123&student_id=456&is_graded=true
- grading-sessions: ?initiated_by=123&status=completed
"""