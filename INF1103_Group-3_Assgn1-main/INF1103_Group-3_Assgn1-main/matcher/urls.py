from django.urls import path

from . import views

app_name = "matcher"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("employer/", views.employer_upload, name="employer_upload"),
    path("employer/results/", views.employer_results, name="employer_results"),
    path("job-seeker/", views.job_seeker_upload, name="job_seeker_upload"),
    path("job-seeker/results/", views.job_results, name="job_results"),
]
