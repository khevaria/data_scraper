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

# Django settings and model imports
from django.conf import settings
from indeed.models import JobRecord

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# For loading cookies
import json


async def load_cookies(context, cookies_file):
    """
    Load cookies from a JSON file and add them to the given browser context.
    Fix any invalid 'sameSite' values to avoid Playwright errors.
    """
    try:
        with open(cookies_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
            for cookie in cookies:
                # Only "None", "Lax", or "Strict" are valid in Playwright
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    logger.warning(
                        f"Invalid sameSite value '{cookie['sameSite']}' "
                        f"for cookie '{cookie['name']}'. Setting to 'Lax'."
                    )
                    cookie['sameSite'] = 'Lax'
            await context.add_cookies(cookies)
            logger.info(f"Cookies loaded successfully from {cookies_file}.")
    except FileNotFoundError:
        logger.warning(f"Cookies file not found: {cookies_file} – skipping cookies load.")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse cookies JSON: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading cookies: {e}")


# A small pool of user agents (add more if desired)
USER_AGENT_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',

    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',

    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',

    'Mozilla/5.0 (X11; Linux x86_64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
]


async def extract_job_ids(
        job_title=None,
        location=None,
        user_agent=None,
        headless=False,  # Run with UI (headed) by default
        base_url="https://ca.indeed.com/jobs",
        network_idle_timeout=60000,
        job_count_class="searchCount",
        job_link_data_attr="data-jk"):

    logger.info("Starting the extraction process...")
    base_url = "https://ca.indeed.com/jobs"
    start_time = timezone.now()
    scrape_session_id = str(uuid.uuid4())
    logger.info(f"Scrape session ID: {scrape_session_id}")

    # Pick a random user agent if none provided
    if not user_agent:
        user_agent = random.choice(USER_AGENT_POOL)

    # Attempt to load extra config from YAML (optional)
    config_path = os.path.join(settings.BASE_DIR, 'indeed', 'config.yaml')
    logger.info(f"Loading configuration from {config_path}")
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.safe_load(config_file)

            # This corresponds to the YAML hierarchy:
            # get_job_ids:
            #   defaults:
            #     user_agent: ...
            job_scraper_config = config['get_job_ids']['defaults']

            # Extract values from your config, with optional fallback to defaults
            user_agent = job_scraper_config.get('user_agent', user_agent)
            headless = job_scraper_config.get('headless', headless)
            base_url = job_scraper_config.get('base_url', base_url)
            network_idle_timeout = job_scraper_config.get('network_idle_timeout', network_idle_timeout)
            job_count_class = job_scraper_config.get('job_count_class', job_count_class)
            job_link_data_attr = job_scraper_config.get('job_link_data_attr', job_link_data_attr)
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")

    # Output directory for CSV
    output_dir = os.path.join(settings.BASE_DIR, 'indeed', 'output', 'pendingExtraction')
    logger.info(f"Output directory: {output_dir}")

    total_job_ids_found = 0
    new_job_ids_saved = 0
    all_job_ids = []

    async with async_playwright() as p:
        logger.info(f"Launching browser with User-Agent: {user_agent}")
        browser = await p.chromium.launch(headless=headless)

        # Create a more realistic browser context
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1366, 'height': 768},
            locale='en-US',
            timezone_id='America/New_York'
        )

        # Set additional HTTP headers
        await context.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Ch-Ua': '"Chromium";v="91", " Not;A Brand";v="99", "Google Chrome";v="91"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"'
        })

        page = await context.new_page()

        # Stealth plugin to mask Playwright signals
        await stealth_async(page)

        # Load cookies from JSON
        cookies_file = os.path.join(settings.BASE_DIR, 'indeed', 'cookies.json')
        await load_cookies(context, cookies_file)

        # Add a random delay to mimic real user "think time"
        delay = random.uniform(2, 4)
        logger.info(f"Sleeping for {delay:.2f} seconds to mimic human behavior...")
        await asyncio.sleep(delay)

        # Minimal mouse movement
        await page.mouse.move(100, 200)
        await page.wait_for_timeout(500)
        await page.mouse.move(200, 300)

        # Construct your search URL
        search_url = f"{base_url}?q={job_title}&l={location}"
        logger.info(f"Navigating to {search_url}...")
        await page.goto(search_url, wait_until='networkidle', timeout=network_idle_timeout)

        # Extract the page content
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # Attempt to parse total jobs
        job_count_elem = soup.find('div', {'class': job_count_class})
        job_count_text = '0'
        if job_count_elem and job_count_elem.find('span'):
            job_count_text = job_count_elem.find('span').text

        match = re.search(r'\d+', job_count_text.replace(',', ''))
        if match:
            total_jobs = int(match.group())
        else:
            total_jobs = 0

        logger.info(f"Total number of jobs: {total_jobs}")

        jobs_per_page = 15
        total_pages = math.ceil(total_jobs / jobs_per_page)
        logger.info(f"Total number of pages: {total_pages}")

        for page_num in range(total_pages):
            start = page_num * 10
            page_url = f'{search_url}&start={start}'
            logger.info(f"Navigating to {page_url}...")
            try:
                await page.goto(page_url, wait_until='networkidle', timeout=network_idle_timeout)
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')

                job_links = soup.find_all('a', {job_link_data_attr: True})
                if not job_links:
                    logger.warning(f"No job links found on page {page_num + 1}. Check HTML structure.")

                for link in job_links:
                    job_id = link[job_link_data_attr]
                    total_job_ids_found += 1

                    # Check if the job ID already exists
                    exists = await sync_to_async(JobRecord.objects.filter(job_id=job_id).exists)()
                    if exists:
                        logger.info(f"Job ID {job_id} already exists in the database. Skipping.")
                    else:
                        job_record = JobRecord(
                            job_id=job_id,
                            source='Indeed',
                            status='Active',
                            retrieved_date=timezone.now(),
                            scrape_session_id=scrape_session_id,
                        )
                        await sync_to_async(job_record.save)()
                        logger.info(f"Job ID {job_id} saved to database.")
                        new_job_ids_saved += 1

                    all_job_ids.append(job_id)

                # Random sleep between pages
                page_delay = random.uniform(1, 2.5)
                logger.info(f"Sleeping for {page_delay:.2f} seconds before the next page...")
                await asyncio.sleep(page_delay)

            except Exception as e:
                logger.error(f"Failed to load page {page_num + 1}: {e}")

        # Generate output CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'indeed_job_ids_{timestamp}.csv'
        output_file_path = os.path.join(output_dir, csv_filename)

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
        await browser.close()
        logger.info("Browser closed. Extraction process completed.")

    end_time = timezone.now()

    result = {
        'message': 'Scraping completed successfully',
        'scrape_session_id': scrape_session_id,
        'total_job_ids_found': total_job_ids_found,
        'new_job_ids_saved': new_job_ids_saved,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'csv_file_name': csv_filename
    }

    return result
