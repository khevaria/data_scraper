# serializers.py
from rest_framework import serializers

class JobDataScrapeRequestSerializer(serializers.Serializer):
    file_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    folder_name = serializers.CharField(max_length=255, required=False, allow_blank=True)