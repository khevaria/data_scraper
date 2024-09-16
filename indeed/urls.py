# indeed/urls.py

from django.urls import path
from .views import scrape_job_ids  # Import the view from views.py

urlpatterns = [
    path('scrape-job-ids/', scrape_job_ids, name='scrape-job-ids'),  # Define the route here
]