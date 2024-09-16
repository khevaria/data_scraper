import asyncio
import logging
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import csv
import math
from playwright_stealth import stealth_async
import re
import yaml
import os
from datetime import datetime
import random
import uuid  # For scrape_session_id
from django.utils import timezone
from asgiref.sync import sync_to_async

# Import settings from Django
from django.conf import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration from YAML file using settings.BASE_DIR
config_path = os.path.join(settings.BASE_DIR, 'indeed', 'config.yaml')
logger.info(f"Loading configuration from {config_path}")

try:
    with open(config_path, 'r') as config_file:
        config = yaml.safe_load(config_file)
        job_scraper_config = config['get_job_ids']['defaults']
except FileNotFoundError as e:
    logger.error(f"Configuration file not found: {e}")
    # Handle the error as needed
except yaml.YAMLError as e:
    logger.error(f"Error parsing YAML configuration: {e}")
    # Handle the error as needed

# Define output directory path using settings.BASE_DIR
output_dir = os.path.join(settings.BASE_DIR, 'indeed', 'output', 'pendingExtraction')

# Log the output directory path
logger.info(f"Output directory: {output_dir}")

# Define a pool of user agents
USER_AGENT_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/90.0.4430.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/89.0.4389.128 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/88.0.4324.150 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/90.0.4430.93 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/89.0.4389.128 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/88.0.4324.150 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/90.0.4430.93 Safari/537.36',
]

# Import your Django model
from indeed.models import JobRecord


async def extract_job_ids(job_title=None, location=None, user_agent=None, headless=None,
                          base_url=None, network_idle_timeout=None, job_count_class=None,
                          job_link_data_attr=None):
    logger.info("Starting the extraction process...")

    # Record the start time
    start_time = timezone.now()

    scrape_session_id = str(uuid.uuid4())
    logger.info(f"Scrape session ID: {scrape_session_id}")

    # If no user agent is provided, select one randomly from the pool
    user_agent = user_agent or random.choice(USER_AGENT_POOL)
    headless = headless if headless is not None else job_scraper_config['headless']
    base_url = base_url or job_scraper_config['base_url']
    network_idle_timeout = network_idle_timeout or job_scraper_config['network_idle_timeout']
    job_count_class = job_count_class or job_scraper_config['job_count_class']
    job_link_data_attr = job_link_data_attr or job_scraper_config['job_link_data_attr']

    # Initialize counters
    total_job_ids_found = 0
    new_job_ids_saved = 0
    all_job_ids = []

    async with async_playwright() as p:
        logger.info("Launching browser with User-Agent: %s", user_agent)
        browser = await p.chromium.launch(headless=headless)

        # Set a realistic User-Agent and create a new page
        context = await browser.new_context(user_agent=user_agent)
        page = await context.new_page()

        # Apply stealth plugin
        await stealth_async(page)

        # Construct the URL for the job search
        search_url = f"{base_url}?q={job_title}&l={location}"

        logger.info(f"Navigating to {search_url}...")
        # Navigate to the search results page and wait for network to be idle
        await page.goto(search_url, wait_until='networkidle', timeout=network_idle_timeout)

        logger.info("Page loaded. Extracting HTML content...")
        # Extract the HTML content
        content = await page.content()

        logger.info("Parsing HTML content with BeautifulSoup...")
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')

        logger.info("Finding total number of jobs...")
        # Find total number of jobs
        job_count_elem = soup.find('div', {'class': job_count_class})
        job_count_text = job_count_elem.find('span').text if job_count_elem else '0'
        total_jobs = int(re.search(r'\d+', job_count_text.replace(',', '')).group())

        logger.info(f"Total number of jobs: {total_jobs}")

        jobs_per_page = 15
        total_pages = math.ceil(total_jobs / jobs_per_page)
        logger.info(f"Total number of pages: {total_pages}")

        for page_num in range(total_pages):
            start = page_num * 10  # Calculate the start parameter
            page_url = f'{search_url}&start={start}'
            logger.info(f"Navigating to {page_url}...")
            try:
                await page.goto(page_url, wait_until='networkidle', timeout=network_idle_timeout)

                logger.info("Page loaded. Extracting HTML content...")
                # Extract the HTML content
                content = await page.content()

                logger.info("Parsing HTML content with BeautifulSoup...")
                # Parse the HTML content using BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')

                logger.info(f"Finding all <a> tags with {job_link_data_attr} attribute...")
                # Find all <a> tags with the job links containing the data-jk attribute
                job_links = soup.find_all('a', {job_link_data_attr: True})

                if not job_links:
                    logger.warning(f"No job links found on page {page_num + 1}. Please check the HTML structure.")

                logger.info("Processing job IDs...")
                for link in job_links:
                    job_id = link[job_link_data_attr]

                    # Increment the total_job_ids_found counter
                    total_job_ids_found += 1

                    # Check if job_id exists in database
                    exists = await sync_to_async(JobRecord.objects.filter(job_id=job_id).exists)()
                    if exists:
                        logger.info(f"Job ID {job_id} already exists in the database. Skipping.")
                    else:
                        # Create new JobRecord
                        job_record = JobRecord(
                            job_id=job_id,
                            source='Indeed',
                            status='Active',
                            retrieved_date=timezone.now(),
                            scrape_session_id=scrape_session_id,
                        )
                        await sync_to_async(job_record.save)()
                        logger.info(f"Job ID {job_id} saved to database.")
                        # Increment the new_job_ids_saved counter
                        new_job_ids_saved += 1

                    # Append the job_id to all_job_ids to write to CSV later
                    all_job_ids.append(job_id)

            except Exception as e:
                logger.error(f"Failed to load page {page_num + 1}: {e}")

        # Generate a timestamp for the filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Create the output CSV filename with the timestamp
        csv_filename = f'indeed_job_ids_{timestamp}.csv'
        output_file_path = os.path.join(output_dir, csv_filename)

        # Save the job IDs to the CSV file in the output directory
        try:
            with open(output_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Job IDs'])
                for job_id in all_job_ids:
                    writer.writerow([job_id])
            logger.info(f"Job IDs have been written to {output_file_path}")
        except Exception as e:
            logger.error(f"Failed to write CSV file at {output_file_path}: {e}")

        logger.info("Closing browser...")
        # Close the browser
        await browser.close()
        logger.info("Browser closed. Extraction process completed.")

    # Record the end time
    end_time = timezone.now()

    # Prepare the result data
    result = {
        'message': 'Scraping completed successfully',
        'scrape_session_id': scrape_session_id,
        'total_job_ids_found': total_job_ids_found,
        'new_job_ids_saved': new_job_ids_saved,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'csv_file_name': csv_filename  # Include the CSV file name
    }

    return result
