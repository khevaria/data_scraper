from django.db import models  # Django's native models
from django.utils import timezone


class JobRecord(models.Model):
    job_id = models.CharField(max_length=255, unique=True)  # Adjusted max_length to avoid MySQL warning
    job_url = models.URLField(max_length=1000, blank=True, null=True)
    job_title = models.CharField(max_length=500, blank=True, null=True)
    company_name = models.CharField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=500, blank=True, null=True)
    salary_raw = models.CharField(max_length=500, blank=True, null=True)
    min_salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    max_salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fixed_salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    salary_unit = models.CharField(max_length=100, blank=True, null=True)
    job_type = models.CharField(max_length=500, blank=True, null=True)
    shift_and_schedule = models.CharField(max_length=1000, blank=True, null=True)
    apply_link = models.URLField(max_length=3000, blank=True, null=True)
    job_description_text = models.TextField(blank=True, null=True)
    job_description_html = models.TextField(blank=True, null=True)
    retrieved_date = models.DateTimeField(default=timezone.now)
    scrape_session_id = models.CharField(max_length=500)
    source = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.job_id} - {self.job_title} - {self.company_name}"

    class Meta:
        indexes = [
            models.Index(fields=['job_id'], name='job_id_index'),
            models.Index(fields=['scrape_session_id'], name='scrape_session_index'),
        ]
