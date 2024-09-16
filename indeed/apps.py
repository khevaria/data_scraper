# indeed/apps.py
from django.apps import AppConfig
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class IndeedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'indeed'

    def ready(self):
        # Base output directory
        output_base_dir = os.path.join(settings.BASE_DIR, 'indeed', 'output')

        # List of subdirectories to create inside the output directory
        subdirectories = ['pendingExtraction', 'completed', 'error']

        # Create the base output directory
        try:
            os.makedirs(output_base_dir, exist_ok=True)
            logger.info(f"Directory created or already exists: {output_base_dir}")
        except Exception as e:
            logger.error(f"Failed to create directory {output_base_dir}: {e}")

        # Create each subdirectory
        for subdirectory in subdirectories:
            dir_path = os.path.join(output_base_dir, subdirectory)
            try:
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"Directory created or already exists: {dir_path}")
            except Exception as e:
                logger.error(f"Failed to create directory {dir_path}: {e}")
