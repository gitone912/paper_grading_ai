# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
import os
import io
import base64
import tempfile
import mimetypes
import traceback
import json

# Third-party tools for conversion and images
from PIL import Image
try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None
try:
    # docx2pdf is optional; used to convert .docx -> .pdf
    from docx2pdf import convert as docx2pdf_convert
except Exception:
    docx2pdf_convert = None

# Groq client
try:
    from groq import Groq
except Exception:
    Groq = None
from .models import Subject, MarkingScheme, QuestionPaper, StudentSubmission, GradingSession
from .serializers import (
    SubjectSerializer, MarkingSchemeSerializer, QuestionPaperSerializer,
    StudentSubmissionSerializer, GradingSessionSerializer
)

class SubjectViewSet(viewsets.ModelViewSet):
    """API for managing subjects"""
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    
    def get_queryset(self):
        """Filter subjects by search query if provided"""
        queryset = Subject.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by('name')

class MarkingSchemeViewSet(viewsets.ModelViewSet):
    """API for managing marking schemes"""
    queryset = MarkingScheme.objects.all()
    serializer_class = MarkingSchemeSerializer
    
    def get_queryset(self):
        """Filter marking schemes by user, subject, or active status"""
        queryset = MarkingScheme.objects.all()
        user_id = self.request.query_params.get('user_id', None)
        subject_id = self.request.query_params.get('subject_id', None)
        is_active = self.request.query_params.get('is_active', None)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
            
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set user_id from request data"""
        serializer.save(user_id=self.request.data.get('user_id'))
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a marking scheme"""
        marking_scheme = self.get_object()
        marking_scheme.is_active = False
        marking_scheme.save()
        return Response({'message': 'Marking scheme deactivated'})

class QuestionPaperViewSet(viewsets.ModelViewSet):
    """API for managing question papers"""
    queryset = QuestionPaper.objects.all()
    serializer_class = QuestionPaperSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        """Filter question papers by user, subject, or processing status"""
        queryset = QuestionPaper.objects.all()
        uploaded_by = self.request.query_params.get('uploaded_by', None)
        subject_id = self.request.query_params.get('subject_id', None)
        is_processed = self.request.query_params.get('is_processed', None)
        
        if uploaded_by:
            queryset = queryset.filter(uploaded_by=uploaded_by)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if is_processed is not None:
            queryset = queryset.filter(is_processed=is_processed.lower() == 'true')
            
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set uploaded_by from request data"""
        serializer.save(uploaded_by=self.request.data.get('uploaded_by'))
    
    @action(detail=True, methods=['post'])
    def process_paper(self, request, pk=None):
        """Process uploaded question paper to extract questions"""
        paper = self.get_object()
        
        if paper.is_processed:
            return Response(
                {'error': 'Paper already processed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert paper file into JPEG pages
        def convert_file_to_images(file_path, max_pages=50):
            """Return list of PIL.Image objects for pages/images in the file."""
            ext = os.path.splitext(file_path)[1].lower()
            images = []

            # PDF
            if ext == ".pdf":
                if convert_from_path is None:
                    raise RuntimeError("pdf2image not installed")

                try:
                    images = convert_from_path(file_path, poppler_path="/opt/anaconda3/bin")
                    if not images:
                        raise RuntimeError("pdf2image returned no images. Check Poppler installation.")
                except Exception as e:
                    raise RuntimeError(f"PDF conversion failed: {e}")

                except Exception as e:
                    raise RuntimeError(f"PDF conversion failed: {e}")
            # DOCX -> use docx2pdf to convert to temp pdf, then pdf2image
            elif ext in ('.docx', '.doc'):
                if docx2pdf_convert is None or convert_from_path is None:
                    raise RuntimeError('docx2pdf or pdf2image not available for doc/docx conversion')
                with tempfile.TemporaryDirectory() as td:
                    tmp_pdf = os.path.join(td, 'converted.pdf')
                    # docx2pdf writes to a directory when given a folder; for a single file it writes next to it.
                    # We'll call convert(file, output) when available.
                    try:
                        docx2pdf_convert(file_path, tmp_pdf)
                    except TypeError:
                        # fallback: some versions accept only input path and output folder
                        docx2pdf_convert(file_path)
                        # try to locate converted pdf next to input
                        guessed = os.path.splitext(file_path)[0] + '.pdf'
                        if os.path.exists(guessed):
                            tmp_pdf = guessed
                    images = convert_from_path(tmp_pdf, fmt='jpeg', poppler_path="/opt/anaconda3/bin")

            # Image files (jpg/png/gif)
            else:
                try:
                    im = Image.open(file_path).convert('RGB')
                    images = [im]
                except Exception as e:
                    raise RuntimeError(f'Unsupported file type for conversion: {ext}')

            # respect max_pages
            return images[:max_pages]

        def images_to_data_urls(images):
            urls = []
            for im in images:
                buf = io.BytesIO()
                im.save(buf, format='JPEG')
                b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                urls.append(f'data:image/jpeg;base64,{b64}')
            return urls

        def call_groq_for_extraction(image_data_urls, mode='questions'):
            if Groq is None:
                raise RuntimeError('groq package not installed')

            client = Groq(api_key="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")

            if mode == 'questions':
                system_content = (
                    "your work is to extract questions from images and return in a json format example "
                    "\n[ {\n            \"question_number\": \"1\",\n            \"question_text\": \"Solve the quadratic equation: x² - 5x + 6 = 0\",\n            \"marks\": 10,\n            \"question_type\": \"short_answer\",\n            \"expected_keywords\": [\"factorization\", \"x=2\", \"x=3\"]\n          },\n          {\n            \"question_number\": \"2\",\n            \"question_text\": \"Find the derivative of f(x) = 3x² + 2x - 1\",\n            \"marks\": 15,\n            \"question_type\": \"short_answer\",\n            \"expected_keywords\": [\"derivative\", \"6x\", \"2\"]\n          } ]"
                )
            else:
                system_content = (
                    "your work is to extract answers from images and return in a json format example "
                    "\n[ {\n            \"question_number\": \"1\",\n            \"answer_text\": \"x=2, x=3\",\n            \"confidence\": 0.95\n          },\n          {\n            \"question_number\": \"2\",\n            \"answer_text\": \"6x + 2\",\n            \"confidence\": 0.9\n          } ]"
                )

            # The model supports up to 5 images per request. Batch the images and
            # aggregate parsed JSON results across batches.
            chunk_size = 5
            aggregated = []
            last_raw = None

            for i in range(0, len(image_data_urls), chunk_size):
                chunk = image_data_urls[i:i + chunk_size]

                # Build message content for this chunk
                user_content = [{"type": "text", "text": ""}]
                for url in chunk:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": url}
                    })

                completion = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=1,
                    top_p=1,
                    stream=False,
                    response_format={"type": "json_object"},
                    stop=None
                )

                # The Groq SDK may return a plain str, dict/list, or a SDK-specific
                # message object (e.g. ChoiceMessage). Normalize into Python
                # primitives (dict/list/str) so it can be json-serialized/stored.
                raw_msg = completion.choices[0].message

                # Normalize common SDK message shapes
                if hasattr(raw_msg, 'to_dict') and callable(getattr(raw_msg, 'to_dict')):
                    parsed = raw_msg.to_dict()
                elif hasattr(raw_msg, 'content'):
                    # many SDKs expose the content on a .content attribute
                    parsed = raw_msg.content
                else:
                    parsed = raw_msg

                last_raw = parsed

                # If we have a JSON string, try to decode it into Python objects
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except Exception:
                        # leave as string if it can't be parsed
                        parsed = parsed

                # Aggregate lists/dicts
                if isinstance(parsed, list):
                    aggregated.extend(parsed)
                elif isinstance(parsed, dict):
                    aggregated.append(parsed)
                else:
                    # For unexpected types (e.g., raw string), keep last_raw for fallback
                    pass

            # Prefer returning aggregated list when we have multiple items,
            # otherwise return the last parsed/raw message to preserve previous behavior.
            if aggregated:
                return aggregated
            # try to return parsed form of last_raw if possible
            if isinstance(last_raw, str):
                try:
                    return json.loads(last_raw)
                except Exception:
                    return last_raw
            return last_raw

        # Try conversion and extraction
        try:
            file_path = paper.paper_file.path
            images = convert_file_to_images(file_path)
            if not images:
                return Response({'error': 'No images/pages extracted from file'}, status=status.HTTP_400_BAD_REQUEST)

            data_urls = images_to_data_urls(images)
            extracted = call_groq_for_extraction(data_urls, mode='questions')

            # Ensure we have a list/dict as expected
            paper.extracted_questions = extracted if isinstance(extracted, list) else (extracted or [])
            # try populate total marks if provided
            try:
                paper.total_marks = sum(int(q.get('marks', 0)) for q in paper.extracted_questions)
            except Exception:
                paper.total_marks = 0

            paper.is_processed = True
            paper.save()

            return Response({
                'message': 'Paper processed successfully',
                'total_marks': paper.total_marks,
                'questions_count': len(paper.extracted_questions)
            })

        except Exception as e:
            tb = traceback.format_exc()
            return Response({'error': str(e), 'trace': tb}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Get extracted questions from a paper"""
        paper = self.get_object()
        if not paper.is_processed:
            return Response(
                {'error': 'Paper not processed yet'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'questions': paper.extracted_questions,
            'total_marks': paper.total_marks
        })

class StudentSubmissionViewSet(viewsets.ModelViewSet):
    """API for managing student submissions"""
    queryset = StudentSubmission.objects.all()
    serializer_class = StudentSubmissionSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        """Filter submissions by question paper, student, or grading status"""
        queryset = StudentSubmission.objects.all()
        question_paper_id = self.request.query_params.get('question_paper_id', None)
        student_id = self.request.query_params.get('student_id', None)
        is_graded = self.request.query_params.get('is_graded', None)
        
        if question_paper_id:
            queryset = queryset.filter(question_paper_id=question_paper_id)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if is_graded is not None:
            queryset = queryset.filter(is_graded=is_graded.lower() == 'true')
            
        return queryset.order_by('-submitted_at')
    
    @action(detail=True, methods=['post'])
    def grade_submission(self, request, pk=None):
        """Grade a single submission"""
        submission = self.get_object()
        
        if submission.is_graded:
            return Response(
                {'error': 'Submission already graded'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not submission.question_paper.is_processed:
            return Response(
                {'error': 'Question paper not processed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert student's answer file into images and call Groq to extract answers
        try:
            answer_file_path = submission.answer_file.path
            # reuse conversion helper defined earlier in file scope by copying logic
            def convert_file_to_images_local(file_path, max_pages=50):
                ext = os.path.splitext(file_path)[1].lower()
                images = []
                if ext == ".pdf":
                    if convert_from_path is None:
                        raise RuntimeError("pdf2image not installed")

                    try:
                        images = convert_from_path(file_path, poppler_path="/opt/anaconda3/bin")
                        if not images:
                            raise RuntimeError("pdf2image returned no images. Check Poppler installation.")
                    except Exception as e:
                        raise RuntimeError(f"PDF conversion failed: {e}")

                    except Exception as e:
                        raise RuntimeError(f"PDF conversion failed: {e}")
                elif ext in ('.docx', '.doc'):
                    if docx2pdf_convert is None or convert_from_path is None:
                        raise RuntimeError('docx2pdf or pdf2image not available for doc/docx conversion')
                    with tempfile.TemporaryDirectory() as td:
                        tmp_pdf = os.path.join(td, 'converted.pdf')
                        try:
                            docx2pdf_convert(file_path, tmp_pdf)
                        except TypeError:
                            docx2pdf_convert(file_path)
                            guessed = os.path.splitext(file_path)[0] + '.pdf'
                            if os.path.exists(guessed):
                                tmp_pdf = guessed
                        images = convert_from_path(tmp_pdf, fmt='jpeg', poppler_path="/opt/anaconda3/bin")
                else:
                    im = Image.open(file_path).convert('RGB')
                    images = [im]
                return images[:max_pages]

            images = convert_file_to_images_local(answer_file_path)
            if not images:
                return Response({'error': 'No images/pages extracted from answer file'}, status=status.HTTP_400_BAD_REQUEST)

            # convert to data urls
            buf_urls = []
            for im in images:
                buf = io.BytesIO()
                im.save(buf, format='JPEG')
                b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                buf_urls.append(f'data:image/jpeg;base64,{b64}')

            extracted_answers = call_groq_for_extraction(buf_urls, mode='answers')

            # Save extracted answers
            submission.extracted_answers = extracted_answers if isinstance(extracted_answers, list) else (extracted_answers or [])

            # Simple scoring: for each question in paper.extracted_questions, check keywords in extracted answer
            question_results = []
            total_marks_obtained = 0
            total_possible = 0

            questions = submission.question_paper.extracted_questions or []
            answers = submission.extracted_answers or []

            # Map answers by question_number for quick lookup
            ans_map = {str(a.get('question_number')): a for a in (answers if isinstance(answers, list) else [])}

            for q in (questions if isinstance(questions, list) else []):
                qnum = str(q.get('question_number'))
                marks_possible = int(q.get('marks', 0)) if q.get('marks') is not None else 0
                total_possible += marks_possible
                ans = ans_map.get(qnum, {})
                ans_text = ans.get('answer_text', '') if isinstance(ans, dict) else ''

                # basic keyword matching
                expected = q.get('expected_keywords', []) or []
                if isinstance(expected, str):
                    expected = [expected]
                matches = 0
                for kw in expected:
                    if kw.lower() in ans_text.lower():
                        matches += 1

                marks_obtained = 0
                if expected:
                    marks_obtained = int(round((matches / len(expected)) * marks_possible))
                else:
                    # if no expected keywords, give full marks if any answer present
                    marks_obtained = marks_possible if ans_text.strip() else 0

                total_marks_obtained += marks_obtained

                question_results.append({
                    'question_number': qnum,
                    'marks_obtained': marks_obtained,
                    'marks_possible': marks_possible,
                    'feedback': f'Matched {matches}/{len(expected) if expected else 1} expected keywords'
                })

            percentage = (total_marks_obtained / total_possible) * 100 if total_possible > 0 else 0

            detailed = {
                'question_results': question_results,
                'overall_feedback': 'Automatic grading complete',
                'extracted_answers': submission.extracted_answers
            }

            submission.detailed_results = detailed
            submission.total_marks = total_marks_obtained
            submission.percentage = percentage
            submission.is_graded = True
            submission.graded_at = timezone.now()
            submission.save()

            return Response({
                'message': 'Submission graded successfully',
                'total_marks': total_marks_obtained,
                'percentage': percentage,
                'detailed_results': detailed
            })

        except Exception as e:
            tb = traceback.format_exc()
            return Response({'error': str(e), 'trace': tb}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """Get grading results for a submission"""
        submission = self.get_object()
        
        if not submission.is_graded:
            return Response(
                {'error': 'Submission not graded yet'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'student_name': submission.student_name,
            'student_id': submission.student_id,
            'total_marks': submission.total_marks,
            'percentage': submission.percentage,
            'detailed_results': submission.detailed_results,
            'graded_at': submission.graded_at
        })

class GradingSessionViewSet(viewsets.ModelViewSet):
    """API for managing grading sessions"""
    queryset = GradingSession.objects.all()
    serializer_class = GradingSessionSerializer
    
    def get_queryset(self):
        """Filter grading sessions by user or status"""
        queryset = GradingSession.objects.all()
        initiated_by = self.request.query_params.get('initiated_by', None)
        status_filter = self.request.query_params.get('status', None)
        
        if initiated_by:
            queryset = queryset.filter(initiated_by=initiated_by)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset.order_by('-started_at')
    
    def perform_create(self, serializer):
        """Set initiated_by from request data"""
        serializer.save(initiated_by=self.request.data.get('initiated_by'))
    
    @action(detail=True, methods=['post'])
    def start_grading(self, request, pk=None):
        """Start grading all submissions for a question paper"""
        session = self.get_object()
        
        if session.status != 'pending':
            return Response(
                {'error': 'Session already started or completed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all ungraded submissions for this question paper
        ungraded_submissions = StudentSubmission.objects.filter(
            question_paper=session.question_paper,
            is_graded=False
        )
        
        session.total_submissions = ungraded_submissions.count()
        session.status = 'processing'
        session.save()
        
        # TODO: Implement batch grading logic here
        # This could be done asynchronously with Celery
        
        return Response({
            'message': 'Grading session started',
            'total_submissions': session.total_submissions,
            'status': session.status
        })
    
    @action(detail=True, methods=['get'])
    def status_check(self, request, pk=None):
        """Check the status of a grading session"""
        session = self.get_object()
        
        # Update processed count
        if session.status == 'processing':
            graded_count = StudentSubmission.objects.filter(
                question_paper=session.question_paper,
                is_graded=True
            ).count()
            session.processed_submissions = graded_count
            
            # Check if all submissions are processed
            if graded_count >= session.total_submissions:
                session.status = 'completed'
                session.completed_at = timezone.now()
            
            session.save()
        
        return Response({
            'status': session.status,
            'total_submissions': session.total_submissions,
            'processed_submissions': session.processed_submissions,
            'progress_percentage': (session.processed_submissions / session.total_submissions * 100) if session.total_submissions > 0 else 0,
            'started_at': session.started_at,
            'completed_at': session.completed_at
        })