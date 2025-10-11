import arxiv
import pdfplumber
import requests
import trafilatura
from io import BytesIO

def fetch_arxiv_abstract(arxiv_id):
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(search.results(), None)
        if result:
            return f"Title: {result.title}\n\nAbstract: {result.summary}"
    except Exception as e:
        print(f"[ERROR] arxiv extraction failed: {e}")
    return None

def fetch_pdf_text(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=15)
        with pdfplumber.open(BytesIO(response.content)) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip() if text else None
    except Exception as e:
        print(f"[ERROR] PDF extraction failed: {e}")
        return None

def fetch_web_text(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            return trafilatura.extract(downloaded)
    except Exception as e:
        print(f"[ERROR] Web extraction failed: {e}")
    return None
