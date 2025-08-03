from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import os
import json


def initiate_webdriver():
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-insecure-localhost')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument("--log-level=3")
    # options.add_argument("--headless")  # Run in headless mode
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) # Use the latest version
    return driver

def get_author(driver):
    try:
        author = driver.find_element(By.CLASS_NAME, 'detail__author').text
    except:
        author = ''
    return author

def get_detail_content(driver):
    try:
        detail_content = driver.find_element(By.CLASS_NAME, 'detail__body-text').text
    except:
        detail_content = ''
    return detail_content

def summarize_result(titles, publishers, media_dates, content_links, authors, detail_contents):

    # Combine into list of dicts
    data = [
        {
            "title": t, 
            "publiser": p,
            "date_publish" : d, 
            "link" : l,
            "author" : a,
            "detail_content" : c
        } 
        for t, p, d, l, a, c in zip(titles, publishers, media_dates, content_links, authors, detail_contents)
    ]

    return data

def read_past_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    return data

