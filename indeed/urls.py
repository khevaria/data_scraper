# indeed/urls.py

from django.urls import path
from .views import scrape_job_ids, scrape_job_data  # Import the view from views.py

urlpatterns = [
    path('scrape-job-ids/', scrape_job_ids, name='scrape-job-ids'),
    path('scrape-job-data/', scrape_job_data, name='scrape-job-data'),
]