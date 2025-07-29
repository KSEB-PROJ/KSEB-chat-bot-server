"""
Selenium 기반 웹 페이지 텍스트 추출 모듈
"""

import asyncio
from typing import List
from bs4 import BeautifulSoup
from langchain.tools import tool

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def fetch_html_by_selenium(url: str) -> str:
    """
    Selenium으로 동적 JS 렌더링 포함 HTML 전체 소스를 반환
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0")
    service = Service(ChromeDriverManager().install())
    driver = None
    html = ""
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        html = driver.page_source
    finally:
        if driver:
            driver.quit()
    return html

async def fetch_text_chunks(url: str, chunk_size: int = 8000) -> List[str]:
    """
    HTML을 BeautifulSoup으로 파싱 후 텍스트만 추출해 chunk로 분할
    """
    html = await asyncio.to_thread(fetch_html_by_selenium, url)
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
        tag.decompose()
    text = soup.get_text(separator='\n', strip=True)
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

@tool
async def read_web_page(url: str) -> List[str]:
    """
    동적 JS 렌더링 포함 웹페이지 전체 텍스트를 8k chunk로 나누어 반환
    """
    try:
        return await fetch_text_chunks(url)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return [f"오류: 웹 페이지를 읽는 중 문제가 발생했습니다: {exc}"]
