
"""Experimental drugs.com scraper (Playwright + BeautifulSoup).

Not used by the production API. Requires ``playwright`` and ``beautifulsoup4``.
"""


# drug_scraper.py

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import csv
import time

def fetch_html_with_playwright(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        html = page.content()
        browser.close()
        return html

def extract_section(soup, start_id="uses", end_id="warnings"):
    start_tag = soup.find("h2", id=start_id)
    end_tag = soup.find("h2", id=end_id)

    if not start_tag or not end_tag:
        return None

    content = []
    current = start_tag.find_next_sibling()

    while current and current != end_tag:
        if current.name in ["p", "ul", "ol", "li"]:
            text = current.get_text(strip=True)
            if text:
                content.append(text)
        current = current.find_next_sibling()

    return "\n".join(content)

def scrape_drug_summary(drug_name):
    base_url = "https://www.drugs.com/"
    drug_url = f"{base_url}{drug_name.lower().replace(' ', '-')}.html"
    try:
        html = fetch_html_with_playwright(drug_url)
        soup = BeautifulSoup(html, "html.parser")
        summary = extract_section(soup)
        return summary or "Section not found"
    except Exception as e:
        return f"Error: {str(e)}"

def scrape_multiple_drugs(drug_list, output_file="drug_summaries.csv"):
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Drug", "Summary"])
        for drug in drug_list:
            print(f"Scraping {drug}...")
            summary = scrape_drug_summary(drug)
            writer.writerow([drug, summary])
            time.sleep(2)  # Be polite to the server

if __name__ == "__main__":
    # Example list of drugs
    drugs = ["paracetamol", "ibuprofen", "amoxicillin", "azithromycin"]
    scrape_multiple_drugs(drugs)
