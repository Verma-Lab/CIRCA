# import requests
# import xml.etree.ElementTree as ET
# from paperscraper import pubmed

# # Metadata
# pmid = "NBK545161"
# metadata = pubmed.get_pubmed_papers([pmid])

# # Fetch PMC article in XML
# pmc_id = "PMCNBK545161"
# base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
# efetch_url = f"{base_url}efetch.fcgi?db=pmc&id={pmc_id}"
# response = requests.get(efetch_url)
# response.raise_for_status()

# # Parse XML
# root = ET.fromstring(response.text)

# # Extract full text with better filtering
# full_text = ""
# for elem in root.findall(".//body//p"):  # Target <p> tags in body for paragraphs
#     if elem.text and elem.text.strip():
#         full_text += elem.text.strip() + "\n\n"
#     # Include text from child elements (e.g., <italic>, <bold>)
#     for child in elem:
#         if child.tail and child.tail.strip():
#             full_text += child.tail.strip() + "\n\n"

# # Combine with metadata
# paper_data = {
#     "metadata": metadata.iloc[0].to_dict() if not metadata.empty else {},
#     "full_text": full_text
# }

# # Save to file
# import json
# with open("pmc3418173_data.json", "w") as f:
#     json.dump(paper_data, f, indent=4)

# print("Full paper data saved to pmc3418173_data.json")
# print("Sample full text (first 500 chars):", full_text[:500])

# import requests
# from bs4 import BeautifulSoup

# # Fetch the Bookshelf page
# url = "https://www.ncbi.nlm.nih.gov/books/NBK545161/"
# response = requests.get(url)
# response.raise_for_status()

# # Parse HTML
# soup = BeautifulSoup(response.text, "html.parser")

# # Extract metadata
# # Title
# title = soup.find("h1", id="NBK545161").get_text(strip=True) if soup.find("h1", id="NBK545161") else "Unknown Title"

# # Authors (clean up the extraction)
# authors_elem = soup.find("p", class_="contrib-group")
# authors = []
# if authors_elem:
#     # Split and clean author names (remove "Authors", numbers, and trailing dots)
#     author_text = authors_elem.get_text(strip=True).replace("Authors", "").replace(".", "")
#     authors = [name.strip() for name in author_text.split(";") if name.strip() and not name.strip().isdigit()]

# # Book (likely in meta-content or breadcrumb)
# book = soup.find("div", class_="meta-content")
# if book:
#     book_link = book.find("a", href=lambda x: x and "books" in x)
#     book = book_link.get_text(strip=True) if book_link else "Unknown Book"
# else:
#     book = "Unknown Book"

# # Date (look for fm-date or meta-content)
# date = soup.find("span", class_="fm-date")
# if date:
#     date = date.get_text(strip=True)
# else:
#     date_elem = soup.find("div", class_="meta-content")
#     date = date_elem.find("span", class_="fm-date").get_text(strip=True) if date_elem and date_elem.find("span", class_="fm-date") else "Unknown Date"

# metadata = {
#     "title": title,
#     "authors": authors,
#     "book": book,
#     "date": date
# }

# # Extract full text (target sections under maincontent by ID)
# main_content = soup.find("div", id="maincontent")
# full_text_sections = main_content.find_all("div", id=lambda x: x and x.startswith("article-27883.s")) if main_content else []
# full_text = "\n\n".join(section.get_text(strip=True) for section in full_text_sections if section.get_text(strip=True))

# # Fallback: If no sections found, try all <p> tags under maincontent
# if not full_text_sections:
#     full_text_sections = main_content.find_all("p") if main_content else []
#     full_text = "\n\n".join(section.get_text(strip=True) for section in full_text_sections if section.get_text(strip=True))

# # Debug output
# print(f"Found {len(full_text_sections)} sections")
# print("Sample full text (first 500 chars):", full_text[:500] if full_text else "No text extracted")

# # Combine data
# paper_data = {
#     "metadata": metadata,
#     "full_text": full_text
# }

# # Save to file
# import json
# with open("nbk545161_data.json", "w") as f:
#     json.dump(paper_data, f, indent=4)

# print("Full paper data saved to nbk545161_data.json")

# import requests
# from bs4 import BeautifulSoup

# # Fetch the Nature article
# url = "https://www.nature.com/articles/s41423-021-00792-8"
# headers = {"User-Agent": "Mozilla/5.0"}  # To avoid being blocked
# response = requests.get(url, headers=headers)
# response.raise_for_status()

# # Parse HTML
# soup = BeautifulSoup(response.text, "html.parser")

# # Extract metadata
# title = soup.find("meta", attrs={"name": "dc.title"})
# title = title["content"] if title else soup.find("h1", class_="c-article-title").get_text(strip=True) if soup.find("h1", class_="c-article-title") else "Unknown Title"

# authors = [meta["content"] for meta in soup.find_all("meta", attrs={"name": "dc.creator"})]
# if not authors:
#     author_list = soup.find("ul", class_="c-article-author-list")
#     authors = [author.get_text(strip=True) for author in author_list.find_all("li")] if author_list else []

# journal = soup.find("meta", attrs={"name": "prism.publicationName"})
# journal = journal["content"] if journal else "Unknown Journal"

# date = soup.find("meta", attrs={"name": "prism.publicationDate"})
# date = date["content"] if date else soup.find("time")["datetime"] if soup.find("time") else "Unknown Date"

# doi = soup.find("meta", attrs={"name": "doi"})
# doi = doi["content"] if doi else soup.find("a", class_="c-bibliographic-information__value").get_text(strip=True) if soup.find("a", class_="c-bibliographic-information__value") else "Unknown DOI"

# metadata = {
#     "title": title,
#     "authors": authors,
#     "journal": journal,
#     "date": date,
#     "doi": doi
# }

# # Extract full text
# main_content = soup.find("div", class_="c-article-body")
# if not main_content:
#     main_content = soup.find("main", id="content")
# full_text_sections = main_content.find_all("section") if main_content else []
# full_text = "\n\n".join(section.get_text(strip=True) for section in full_text_sections if section.get_text(strip=True))

# # Debug output
# print(f"Found {len(full_text_sections)} sections")
# print("Sample full text (first 500 chars):", full_text[:500] if full_text else "No text extracted")

# # Combine data
# paper_data = {
#     "metadata": metadata,
#     "full_text": full_text
# }

# # Save to file
# import json
# with open("nature_s41423-021-00792-8_data.json", "w") as f:
#     json.dump(paper_data, f, indent=4)

# print("Full paper data saved to nature_s41423-021-00792-8_data.json")
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from paperscraper import pubmed
from urllib.parse import urlparse
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

# Function to fetch PMC article (E-utilities)
def fetch_pmc(pmc_id, pmid):
    metadata = pubmed.get_pubmed_papers([pmid])
    metadata_dict = metadata.iloc[0].to_dict() if not metadata.empty else {}
    
    efetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmc_id}"
    response = requests.get(efetch_url)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    full_text = ""
    for elem in root.findall(".//body//p"):
        if elem.text and elem.text.strip():
            full_text += elem.text.strip() + "\n\n"
        for child in elem:
            if child.tail and child.tail.strip():
                full_text += child.tail.strip() + "\n\n"
    return {"metadata": metadata_dict, "full_text": full_text}

# Function to fetch Bookshelf article (HTML scraping)
def fetch_bookshelf(nbk_id, url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Request Error for {url}: {e}")
        return {"metadata": {"title": "Request Failed", "authors": [], "book": "Unknown", "date": "Unknown"}, "full_text": ""}
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    title = soup.find("h1", id=f"NBK{nbk_id}").get_text(strip=True) if soup.find("h1", id=f"NBK{nbk_id}") else "Unknown Title"
    authors_elem = soup.find("p", class_="contrib-group")
    authors = []
    if authors_elem:
        author_text = authors_elem.get_text(strip=True).replace("Authors", "").replace(".", "")
        authors = [name.strip() for name in author_text.split(";") if name.strip() and not name.strip().isdigit()]
    book = soup.find("div", class_="meta-content")
    if book:
        book_link = book.find("a", href=lambda x: x and "books" in x)
        book = book_link.get_text(strip=True) if book_link else "Unknown Book"
    else:
        book = "Unknown Book"
    date = soup.find("span", class_="fm-date")
    if date:
        date = date.get_text(strip=True)
    else:
        date_elem = soup.find("div", class_="meta-content")
        date = date_elem.find("span", class_="fm-date").get_text(strip=True) if date_elem and date_elem.find("span", class_="fm-date") else "Unknown Date"
    metadata = {"title": title, "authors": authors, "book": book, "date": date}
    
    main_content = soup.find("div", id="maincontent")
    full_text_sections = main_content.find_all("div", id=lambda x: x and x.startswith("article-27883.s")) if main_content else []
    full_text = "\n\n".join(section.get_text(strip=True) for section in full_text_sections if section.get_text(strip=True))
    
    if not full_text_sections:
        full_text_sections = main_content.find_all("p") if main_content else []
        full_text = "\n\n".join(section.get_text(strip=True) for section in full_text_sections if section.get_text(strip=True))
    
    return {"metadata": metadata, "full_text": full_text}

# Generic extractor for any webpage
def extract_generic(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"HTTP 404 for {url}: Page not found, skipping")
            return {"metadata": {"title": "Page Not Found", "authors": [], "journal": urlparse(url).netloc, "date": "Unknown", "doi": "Unknown"}, "full_text": ""}
        elif e.response.status_code == 403:
            # Retry 403s with beefier headers
            print(f"403 for {url}, retrying with extra headers")
            headers["Cookie"] = "CONSENT=YES+1"
            headers["Accept-Encoding"] = "gzip, deflate, br"
            headers["Upgrade-Insecure-Requests"] = "1"
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
            except requests.exceptions.RequestException:
                print(f"Retry failed for {url}")
                return {"metadata": {"title": "Access Denied", "authors": [], "journal": urlparse(url).netloc, "date": "Unknown", "doi": "Unknown"}, "full_text": ""}
        else:
            print(f"HTTP Error for {url}: {e}")
            return {"metadata": {"title": "Access Denied", "authors": [], "journal": urlparse(url).netloc, "date": "Unknown", "doi": "Unknown"}, "full_text": ""}
    except requests.exceptions.RequestException as e:
        print(f"Request Error for {url}: {e}")
        return {"metadata": {"title": "Request Failed", "authors": [], "journal": urlparse(url).netloc, "date": "Unknown", "doi": "Unknown"}, "full_text": ""}
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Metadata (try Open Graph, Dublin Core, then site-specific)
    title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "dc.title"})
    title = title["content"] if title else soup.find("h1").get_text(strip=True) if soup.find("h1") else "Unknown Title"
    
    authors = [meta["content"] for meta in soup.find_all("meta", attrs={"name": "dc.creator"})]
    if not authors:
        author_elem = soup.find("meta", property="article:author") or soup.find("meta", attrs={"name": "author"})
        authors = [author_elem["content"]] if author_elem else []
    
    journal = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "prism.publicationName"})
    journal = journal["content"] if journal else "Unknown Journal"
    
    date = soup.find("meta", property="article:published_time") or soup.find("meta", attrs={"name": "prism.publicationDate"})
    date = date["content"] if date else soup.find("time").get("datetime") if soup.find("time") else "Unknown Date"
    
    doi = soup.find("meta", attrs={"name": "doi"})
    doi = doi["content"] if doi else "Unknown DOI"
    
    metadata = {
        "title": title,
        "authors": authors,
        "journal": journal,
        "date": date,
        "doi": doi
    }
    
    # Full text (heuristic: largest div with p tags, or schema.org Article)
    article = soup.find("article") or soup.find("div", attrs={"itemtype": "http://schema.org/Article"})
    if article:
        full_text_sections = article.find_all("p")
    else:
        divs = soup.find_all("div")
        max_p_count = 0
        main_content = None
        for div in divs:
            p_count = len(div.find_all("p"))
            if p_count > max_p_count:
                max_p_count = p_count
                main_content = div
        full_text_sections = main_content.find_all("p") if main_content else soup.find_all("p")
    
    full_text = "\n\n".join(section.get_text(strip=True) for section in full_text_sections if section.get_text(strip=True))
    
    return {"metadata": metadata, "full_text": full_text}

# ScienceDirect-specific extractor with Selenium fallback
def fetch_sciencedirect(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive"
    }
    
    # First try with requests
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error for {url}: {e}. Falling back to Selenium...")
        
        # Use Selenium as a fallback
        options = Options()
        # Comment out headless mode to make it less detectable
        # options.add_argument("--headless")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
        # Add arguments to bypass bot detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        try:
            driver = webdriver.Chrome(options=options)
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
            driver.get(url)
            time.sleep(5)  # Wait for JavaScript to load and cookies to be set
            html = driver.page_source
            driver.quit()
        except Exception as e:
            print(f"Selenium Error for {url}: {e}")
            return {"metadata": {"title": "Access Denied", "authors": [], "journal": "ScienceDirect", "date": "Unknown", "doi": "Unknown"}, "full_text": ""}
    except requests.exceptions.RequestException as e:
        print(f"Request Error for {url}: {e}")
        return {"metadata": {"title": "Request Failed", "authors": [], "journal": "ScienceDirect", "date": "Unknown", "doi": "Unknown"}, "full_text": ""}
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Check if the page is still showing an unsupported browser message
    if "unsupported_browser" in html.lower():
        return {"metadata": {"title": "Unsupported Browser", "authors": [], "journal": "ScienceDirect", "date": "Unknown", "doi": "Unknown"}, "full_text": "ScienceDirect blocked access due to an unsupported browser."}
    
    # Metadata
    title = soup.find("h1", class_="Head").get_text(strip=True) if soup.find("h1", class_="Head") else "Unknown Title"
    authors = [author.get_text(strip=True) for author in soup.find_all("span", class_="author-name") if author.get_text(strip=True)]
    journal = "ScienceDirect"
    date = soup.find("div", class_="publication-date")
    date = date.get_text(strip=True) if date else "Unknown Date"
    doi = soup.find("a", class_="DoiLink")
    doi = doi.get_text(strip=True) if doi else "Unknown DOI"
    
    metadata = {
        "title": title,
        "authors": authors,
        "journal": journal,
        "date": date,
        "doi": doi
    }
    
    # Full text (for topic pages, content is often under <div class="section"> or <div class="content">)
    main_content = soup.find("div", class_="content") or soup.find("div", class_="section")
    full_text_sections = main_content.find_all("p") if main_content else soup.find_all("p")
    full_text = "\n\n".join(section.get_text(strip=True) for section in full_text_sections if section.get_text(strip=True))
    
    return {"metadata": metadata, "full_text": full_text}

# Universal extractor
def universal_extractor(url, article_id=None, pmid=None):
    domain = urlparse(url).netloc
    
    # PMC
    if "ncbi.nlm.nih.gov" in domain and "/pmc/articles/" in url:
        pmc_id = article_id or url.split("/")[-2]
        pmid = pmid or url.split("/")[-2].replace("PMC", "")
        return fetch_pmc(pmc_id, pmid)
    
    # Bookshelf
    elif "ncbi.nlm.nih.gov" in domain and "/books/" in url:
        nbk_id = article_id or url.split("/")[-2]
        return fetch_bookshelf(nbk_id, url)
    
    # Nature
    elif "nature.com" in domain:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Request Error for {url}: {e}")
            return {"metadata": {"title": "Request Failed", "authors": [], "journal": "Nature", "date": "Unknown", "doi": "Unknown"}, "full_text": ""}
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = soup.find("meta", attrs={"name": "dc.title"})
        title = title["content"] if title else soup.find("h1", class_="c-article-title").get_text(strip=True) if soup.find("h1", class_="c-article-title") else "Unknown Title"
        
        authors = [meta["content"] for meta in soup.find_all("meta", attrs={"name": "dc.creator"})]
        if not authors:
            author_list = soup.find("ul", class_="c-article-author-list")
            authors = [author.get_text(strip=True) for author in author_list.find_all("li")] if author_list else []
        
        journal = soup.find("meta", attrs={"name": "prism.publicationName"})
        journal = journal["content"] if journal else "Nature"
        
        date = soup.find("meta", attrs={"name": "prism.publicationDate"})
        date = date["content"] if date else soup.find("time")["datetime"] if soup.find("time") else "Unknown Date"
        
        doi = soup.find("meta", attrs={"name": "doi"})
        doi = doi["content"] if doi else soup.find("a", class_="c-bibliographic-information__value").get_text(strip=True) if soup.find("a", class_="c-bibliographic-information__value") else "Unknown DOI"
        
        metadata = {
            "title": title,
            "authors": authors,
            "journal": journal,
            "date": date,
            "doi": doi
        }
        
        main_content = soup.find("div", class_="c-article-body") or soup.find("main", id="content")
        full_text_sections = main_content.find_all("section") if main_content else []
        full_text = "\n\n".join(section.get_text(strip=True) for section in full_text_sections if section.get_text(strip=True))
        
        return {"metadata": metadata, "full_text": full_text}
    
    # ScienceDirect
    elif "sciencedirect.com" in domain:
        return fetch_sciencedirect(url)
    
    # Generic
    else:
        return extract_generic(url)

# Test with multiple articles
# Test with multiple articles
# articles = [
#     ("PMC3418173", "22915848", "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3418173/"),
#     ("NBK545161", None, "https://www.ncbi.nlm.nih.gov/books/NBK545161/"),
#     (None, None, "https://www.nature.com/articles/s41423-021-00792-8"),
#     (None, None, "https://www.sciencedirect.com/topics/agricultural-and-biological-sciences/protein-synthesis"),
#     (None, None, "https://phys.org/news/2025-03-rna-origami-technique-nanotubes-artificial.html"),  # Added comma here
#     ("PMC6719597", "30082466", "https://pmc.ncbi.nlm.nih.gov/articles/PMC6719597/")
# ]

# for article_id, pmid, url in articles:
#     data = universal_extractor(url, article_id, pmid)
#     filename = f"{article_id or urlparse(url).path.split('/')[-1]}_data.json"
    
#     # Save to file
#     with open(filename, "w") as f:
#         json.dump(data, f, indent=4)
#     print(f"Full paper data saved to {filename}")