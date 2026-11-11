from django.urls import path

from . import views

app_name = "matcher"

urlpatterns = [
    path("", views.LandingView.as_view(), name="landing"),
    path("employer/", views.EmployerUploadView.as_view(), name="employer_upload"),
    path("employer/results/", views.EmployerResultsView.as_view(), name="employer_results"),
    path("job-seeker/", views.JobSeekerUploadView.as_view(), name="job_seeker_upload"),
    path("job-seeker/results/", views.JobResultsView.as_view(), name="job_results"),
]
