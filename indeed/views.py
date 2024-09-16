# views.py
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view
from .serializers import job_id_scrape_serializer
from .scripts.scrape_job_ids import extract_job_ids
from asgiref.sync import async_to_sync  # Import async_to_sync

@api_view(['POST'])
def scrape_job_ids(request):
    # Serialize and validate the incoming request data
    serializer = job_id_scrape_serializer.JobIdScrapeRequestSerializer(data=request.data)
    if serializer.is_valid():
        # Extract the validated data
        params = serializer.validated_data

        # Extract each parameter (passing None will default to config values)
        job_title = params.get('job_title')
        location = params.get('location')
        user_agent = params.get('user_agent')
        headless = params.get('headless')
        base_url = params.get('base_url')
        network_idle_timeout = params.get('network_idle_timeout')
        job_count_class = params.get('job_count_class')
        job_link_data_attr = params.get('job_link_data_attr')

        # Run the async task using async_to_sync and capture the result
        result = async_to_sync(extract_job_ids)(
            job_title=job_title,
            location=location,
            user_agent=user_agent,
            headless=headless,
            base_url=base_url,
            network_idle_timeout=network_idle_timeout,
            job_count_class=job_count_class,
            job_link_data_attr=job_link_data_attr
        )

        # Return the result in the JsonResponse
        return JsonResponse(result, status=status.HTTP_200_OK)
    else:
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
