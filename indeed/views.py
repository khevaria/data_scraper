# views.py
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view
from .serializers import job_id_scrape_serializer, job_data_scrape_serializer
from .scripts.scrape_job_ids import extract_job_ids
from asgiref.sync import async_to_sync  # Import async_to_sync
import os
from django.conf import settings
import shutil
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


@api_view(['POST'])
def scrape_job_data(request):
    # Serialize and validate the incoming request data
    serializer = job_data_scrape_serializer.JobDataScrapeRequestSerializer(data=request.data)
    if serializer.is_valid():
        # Extract the validated data
        file_name = serializer.validated_data.get('file_name')
        folder_name = serializer.validated_data.get('folder_name', 'pendingExtraction')  # Default folder is 'pendingExtraction'

        # Define the base directory and folder paths
        output_base_dir = os.path.join(settings.BASE_DIR, 'indeed', 'output')
        folder_path = os.path.join(output_base_dir, folder_name)
        completed_folder_path = os.path.join(output_base_dir, 'completed')  # Target folder

        # Ensure the 'completed' folder exists
        os.makedirs(completed_folder_path, exist_ok=True)

        # Declare the list outside the loop to store all processed file names
        processed_files = []

        # If file_name is not provided, look for files in the folder
        if not file_name:
            try:
                # List all files in the folder
                files_in_folder = os.listdir(folder_path)
                files_in_folder = [f for f in files_in_folder if os.path.isfile(os.path.join(folder_path, f))]

                if len(files_in_folder) == 0:
                    return JsonResponse({'message': "No file found for which extraction is pending, Please provide a file and folder name"}, status=status.HTTP_404_NOT_FOUND)

                # Process each file in the folder
                for file_in_folder in files_in_folder:
                    file_path = os.path.join(folder_path, file_in_folder)
                    try:
                        with open(file_path, 'r') as file:
                            # Placeholder for file processing logic
                            file_content = file.read()

                        # Append the processed file name to the list
                        processed_files.append(file_in_folder)

                        # Move the file to the 'completed' folder after processing
                        shutil.move(file_path, os.path.join(completed_folder_path, file_in_folder))
                        logger.info(f"File {file_in_folder} moved to completed folder.")

                    except Exception as e:
                        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # After processing all files, return the response
                processed_files_str = ', '.join(processed_files)  # Join processed file names into a single string
                return JsonResponse({
                    'message': f"Files processed and moved successfully: {processed_files_str}",
                    'folder_name': folder_name,
                    'processed_files': processed_files_str
                }, status=status.HTTP_200_OK)

            except FileNotFoundError:
                return JsonResponse({'error': f"Folder {folder_name} not found"}, status=status.HTTP_404_NOT_FOUND)

        # If file_name is provided, process that specific file
        else:
            file_path = os.path.join(folder_path, file_name)

            # Check if the file exists
            if not os.path.exists(file_path):
                return JsonResponse({'error': f'File {file_name} not found in folder {folder_name}'}, status=status.HTTP_404_NOT_FOUND)

            # Process the provided file
            try:
                with open(file_path, 'r') as file:
                    # Placeholder for file processing logic
                    file_content = file.read()

                # Move the file to the 'completed' folder after processing
                shutil.move(file_path, os.path.join(completed_folder_path, file_name))
                logger.info(f"File {file_name} moved to completed folder.")

                # Return success response
                return JsonResponse({
                    'message': f"File {file_name} processed and moved successfully",
                    'file_name': file_name,
                    'folder_name': folder_name
                }, status=status.HTTP_200_OK)

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    else:
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)