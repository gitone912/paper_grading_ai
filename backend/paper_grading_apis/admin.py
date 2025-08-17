from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(Subject)
admin.site.register(MarkingScheme)
admin.site.register(QuestionPaper)
admin.site.register(StudentSubmission)
admin.site.register(GradingSession)