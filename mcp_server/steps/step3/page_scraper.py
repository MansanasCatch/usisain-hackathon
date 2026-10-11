from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup


def fetch_page_content(url: str, timeout: int = 2) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join((chunk for chunk in chunks if chunk))
            return text[:1500]
    except Exception:
        pass
    return ""


def fetch_multiple_pages(urls: list[str]) -> dict[str, str]:
    pages = {}
    with ThreadPoolExecutor(max_workers=max(1, min(3, len(urls)))) as executor:
        future_to_url = {executor.submit(fetch_page_content, url): url for url in urls}
        for future in future_to_url:
            url = future_to_url[future]
            try:
                content = future.result()
                if content:
                    pages[url] = content
            except Exception:
                pass
    return pages
