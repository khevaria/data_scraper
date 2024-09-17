import asyncio
import logging
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import csv
import re
from playwright_stealth import stealth_async
import json
import os
import random
from data_scrapper import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENT_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/90.0.4430.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/89.0.4389.128 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/91.0.4472.124 Safari/537.36',
]

# Function to load cookies from JSON file and ensure correct sameSite attribute
async def load_cookies(page, cookies_file):
    logger.info(f"Loading cookies from {cookies_file}...")
    with open(cookies_file, 'r') as f:
        cookies = json.load(f)
        for cookie in cookies:
            if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                logger.warning(f"Invalid sameSite value '{cookie['sameSite']}' for cookie '{cookie['name']}'. Setting to 'Lax'.")
                cookie['sameSite'] = 'Lax'  # Set to a default valid value like 'Lax'
        await page.context.add_cookies(cookies)
    logger.info("Cookies loaded successfully.")

# Function to read job IDs from the CSV file
def read_job_ids_from_file(file_path):
    job_ids = []
    with open(file_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        # Skip the header
        next(reader, None)
        # Read job IDs line by line
        for row in reader:
            if row:  # Make sure row is not empty
                job_ids.append(row[0])
    return job_ids

# Update function to take file path as input
async def extract_job_details(file_path):
    logger.info("Starting the extraction process...")

    # Load job IDs from file
    job_ids = read_job_ids_from_file(file_path)

    async with async_playwright() as p:
        logger.info("Launching Chromium browser with persistent context...")

        # Launch a persistent Chromium browser (uses Playwright's built-in Chromium)
        browser = await p.chromium.launch(headless=True)
        user_agent = random.choice(USER_AGENT_POOL)
        # Create a new browser context
        context = await browser.new_context(user_agent=user_agent)

        page = await context.new_page()

        # Optional: Apply stealth plugin
        await stealth_async(page)

        # Load cookies from the JSON file
        cookies_file = os.path.join(settings.BASE_DIR, 'cookies.json')  # Set the path to cookies file
        await load_cookies(page, cookies_file)

        job_data = []

        for job_id in job_ids:
            job_url = f"https://ca.indeed.com/viewjob?jk={job_id}"
            logger.info(f"Navigating to job URL: {job_url}...")
            try:
                await page.goto(job_url, wait_until='networkidle', timeout=60000)

                logger.info("Page loaded. Extracting job details...")
                # Extract the HTML content of the job details page
                job_content = await page.content()

                job_soup = BeautifulSoup(job_content, 'html.parser', from_encoding='utf-8')

                # Extract job details
                job_title = job_soup.find('h1', class_='jobsearch-JobInfoHeader-title').text.strip() if job_soup.find('h1', class_='jobsearch-JobInfoHeader-title') else 'N/A'
                company_name = job_soup.find('div', {'data-company-name': 'true'}).text.strip() if job_soup.find('div', {'data-company-name': 'true'}) else 'N/A'
                location = job_soup.find('div', {'data-testid': 'inlineHeader-companyLocation'}).text.strip() if job_soup.find('div', {'data-testid': 'inlineHeader-companyLocation'}) else 'N/A'

                # Extract and parse salary
                salary_text = job_soup.find('span', class_='css-19j1a75').text.strip() if job_soup.find('span', class_='css-19j1a75') else 'N/A'
                min_salary, max_salary, salary_unit = 'N/A', 'N/A', 'N/A'

                if salary_text != 'N/A':
                    # Enhanced regex to capture multi-word units
                    # Attempt to match a salary range with decimals
                    range_match = re.search(
                        r'\$([\d,]+(?:\.\d+)?)\s*[–-]\s*\$([\d,]+(?:\.\d+)?)\s*(?:per\s+|an?\s+)?([a-zA-Z\s]+)',
                        salary_text,
                        re.IGNORECASE
                    )
                    if range_match:
                        min_salary = range_match.group(1).replace(',', '')
                        max_salary = range_match.group(2).replace(',', '')
                        salary_unit_raw = range_match.group(3).strip().lower()
                    else:
                        # Attempt to match a fixed salary with decimals
                        fixed_match = re.search(
                            r'\$([\d,]+(?:\.\d+)?)\s*(?:per\s+|an?\s+)?([a-zA-Z\s]+)',
                            salary_text,
                            re.IGNORECASE
                        )
                        if fixed_match:
                            min_salary = max_salary = fixed_match.group(1).replace(',', '')
                            salary_unit_raw = fixed_match.group(2).strip().lower()

                    if salary_unit_raw:
                        # Map the raw unit to standardized unit using substring matching
                        salary_units = {
                            'year': 'year',
                            'annually': 'year',
                            'month': 'month',
                            'monthly': 'month',
                            'week': 'week',
                            'weekly': 'week',
                            'day': 'day',
                            'daily': 'day',
                            'hour': 'hour',
                            'hourly': 'hour',
                            'per hour': 'hour',
                            'per year': 'year',
                            'per month': 'month',
                            'per week': 'week',
                            'per day': 'day'
                        }
                        # Initialize as 'other'
                        salary_unit = 'other'
                        # Iterate through the salary_units dictionary to find a match
                        for keyword, unit in salary_units.items():
                            if keyword in salary_unit_raw:
                                salary_unit = unit
                                break
                        else:
                            # Log unrecognized units for further analysis
                            logger.warning(f"Unrecognized salary unit '{salary_unit_raw}' in salary text '{salary_text}' for job URL {job_url}.")

                # Extract job type
                job_type = 'N/A'
                for section in job_soup.find_all('div', class_='js-match-insights-provider-e6s05i'):
                    header = section.find('h3', class_='js-match-insights-provider-11n8e9a e1tiznh50')
                    if header and header.text.strip() == "Job type":
                        job_types = [div.text.strip() for div in section.find_all('div', class_='js-match-insights-provider-tvvxwd ecydgvn1') if div.text.strip()]
                        job_type = ', '.join(job_types) if job_types else 'N/A'
                        break

                # Extract shift and schedule
                shift_and_schedule = 'N/A'
                for section in job_soup.find_all('div', class_='js-match-insights-provider-e6s05i'):
                    header = section.find('h3', class_='js-match-insights-provider-11n8e9a e1tiznh50')
                    if header and header.text.strip() == "Shift and schedule":
                        shifts = [div.text.strip() for div in section.find_all('div', class_='js-match-insights-provider-tvvxwd ecydgvn1') if div.text.strip()]
                        shift_and_schedule = ', '.join(shifts) if shifts else 'N/A'
                        break

                # Determine the apply link type
                apply_link = 'N/A'
                apply_button = job_soup.find('button', id='indeedApplyButton')
                if apply_button:
                    apply_link = "Indeed Easy Apply"
                else:
                    # Search for a button with the specific classes and extract the href
                    external_apply_button = job_soup.find('button', class_='css-1oxck4n e8ju0x51')
                    if external_apply_button and 'href' in external_apply_button.attrs:
                        apply_link = external_apply_button['href']

                        # Navigate to the redirect link to get the final URL
                        await page.goto(apply_link, wait_until='networkidle', timeout=60000)
                        final_url = page.url
                        apply_link = final_url  # Update apply_link with the final URL

                # Extract and preserve job description formatting (HTML)
                job_description_element = job_soup.find('div', id='jobDescriptionText')
                job_description_html = job_description_element.decode_contents().strip() if job_description_element else 'N/A'
                compact_html_content = re.sub(r'\s+', ' ', job_description_html).strip()

                # **New Step**: Extract job description as plain text
                job_description_text = job_description_element.get_text(separator=' ', strip=True) if job_description_element else 'N/A'

                # Append the extracted details to the job_data list
                job_data.append({
                    'Job URL': job_url,
                    'Job Title': job_title,
                    'Company Name': company_name,
                    'Location': location,
                    'Salary Text': salary_text,
                    'Min Salary': min_salary,
                    'Max Salary': max_salary,
                    'Salary Unit': salary_unit,
                    'Job Type': job_type,
                    'Shift and Schedule': shift_and_schedule,
                    'Apply Link': apply_link,
                    'Job Description': compact_html_content,
                    'Job Description Text': job_description_text  # **New Column**
                })
            except Exception as e:
                logger.error(f"Error extracting job details from {job_url}: {e}")

        # **Update Fieldnames** to include the new column
        output_csv = os.path.join(os.path.dirname(file_path), 'job_data.csv')
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Job URL',
                'Job Title',
                'Company Name',
                'Location',
                'Salary Text',
                'Min Salary',
                'Max Salary',
                'Salary Unit',
                'Job Type',
                'Shift and Schedule',
                'Apply Link',
                'Job Description',
                'Job Description Text'  # **New Fieldname**
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for job in job_data:
                writer.writerow(job)

        logger.info(f"Job data has been written to {output_csv}")
        logger.info("Closing browser...")
        # Close the browser context (not the entire browser)
        await context.close()
        logger.info("Browser closed. Extraction process completed.")

# Entry point for the script
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python extract_job_details.py <path_to_job_ids_csv>")
    else:
        file_path = sys.argv[1]
        asyncio.run(extract_job_details(file_path))
