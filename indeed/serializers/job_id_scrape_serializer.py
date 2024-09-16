# job_id_scrape_serializer.py
from rest_framework import serializers

class JobIdScrapeRequestSerializer(serializers.Serializer):
    job_title = serializers.CharField(max_length=1000, required=True)
    location = serializers.CharField(max_length=1000, required=True)
    user_agent = serializers.CharField(max_length=1000, required=False, default=None)
    headless = serializers.BooleanField(required=False, default=None)
    base_url = serializers.URLField(required=False, default=None)
    network_idle_timeout = serializers.IntegerField(required=False, default=None)
    job_count_class = serializers.CharField(max_length=1000, required=False, default=None)
    job_link_data_attr = serializers.CharField(max_length=1000, required=False, default=None)