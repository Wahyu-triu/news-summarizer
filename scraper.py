from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import *
import time
import json

class NewsScraper():
    def __init__(self, topic, max_page):
        self.topic = topic
        self.max_page = max_page
        print(f'Initialize scraper for topic : {topic}')
        self.driver = self.driver_initialize()
    
    def driver_initialize(self):
        print('Initialize Driver')
        driver = initiate_webdriver()
        return driver

    def scrap_link(self, page):
        driver = self.driver
        url = "https://www.detik.com/search/searchall?query={}&page={}".format(self.topic, page)
        driver.get(url)

        time.sleep(10) 

        all_content = driver.find_elements(By.XPATH, '//*[@id="nhl"]/div[2]') 

        titles, publishers, media_dates, content_links = [], [], [], []

        print('Scrap Link ...')
        for content in all_content:
            news_collections = content.find_elements(By.CLASS_NAME, 'list-content__item')
            for news in news_collections:
                all_media = news.find_elements(By.CLASS_NAME, 'media')
                for media in all_media:
                    media_text = media.find_elements(By.CLASS_NAME, 'media__text')
                    for item in media_text:
                        title = item.find_element(By.CLASS_NAME, 'media__title').text
                        publisher = item.find_element(By.CLASS_NAME, 'media__subtitle').text
                        media_date = item.find_element(By.CLASS_NAME, 'media__date').text
                        # print(f'Get news link with title : {title}')
                        titles.append(title)
                        publishers.append(publisher)
                        media_dates.append(media_date)
                        link_element = item.find_element(By.TAG_NAME, "a")
                        content_link = link_element.get_attribute("href")
                        content_links.append(content_link)
            
        return titles, publishers, media_dates, content_links

    def scrap_content(self, content_links):
        print('Scrap Content ...')
        driver = self.driver

        authors, detail_contents = [], []
        for link in content_links:
            print(f'Get detail information from : {link}')
            try:
                driver.get(link)
                WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "div.container"))
                )
                # WebDriverWait(driver, 20).until(
                #     lambda d: d.execute_script("return document.readyState") == "complete"
                # )
                author, detail_content = get_author(driver), get_detail_content(driver)
            except Exception as e:
                print(e)
                author, detail_content = '', ''

            authors.append(author)
            detail_contents.append(detail_content)
        
        return authors, detail_contents

    def stop_scrap(self):
        print('Stop Driver')
        self.driver.quit()
    
    def go_to_next_page(self):
        next_button = self.driver.find_element(By.XPATH, "//a[contains(@class, 'pagination__item') and text()='Next']")
        time.sleep(3)
        next_button.click()
    
    def compile_all_scraping_process(self):

        for page in range(self.max_page):

            page_num = page + 1
            print(f'Scrap data for page number : {page_num}')
            general_data = self.scrap_link(page_num)
            titles, publishers, media_dates, content_links = general_data[0], general_data[1], general_data[2], general_data[3]
            
            news_content = self.scrap_content(content_links)
            authors, detail_contents = news_content[0], news_content[1]

            data = summarize_result(titles, publishers, media_dates, content_links, authors, detail_contents)
            past_data = read_past_data("data.json")
            data.extend(past_data)

            with open("data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            # self.go_to_next_page()
            time.sleep(5)

def RunScraper(topic, max_page):
    # Run All Method
    scraper = NewsScraper(topic, max_page)
    scraper.compile_all_scraping_process()
    scraper.stop_scrap()

if __name__ == "__main__":
    RunScraper(topic='ekonomi', max_page=2)

# topic = 'politik'
# url = "https://www.detik.com/search/searchall?query={}".format(topic)

# driver = initiate_webdriver()
# driver.get(url)

# time.sleep(10) 

# all_content = driver.find_elements(By.XPATH, '//*[@id="nhl"]/div[2]') 

# titles, sub_titles, media_dates, content_links = [], [], [], []

# print('Get general information...')
# for content in all_content:
#     news_collections = content.find_elements(By.CLASS_NAME, 'list-content__item')
#     for news in news_collections:
#         all_media = news.find_elements(By.CLASS_NAME, 'media')
#         for media in all_media:
#             media_text = media.find_elements(By.CLASS_NAME, 'media__text')
#             for item in media_text:
#                 title = item.find_element(By.CLASS_NAME, 'media__title').text
#                 sub_title = item.find_element(By.CLASS_NAME, 'media__subtitle').text
#                 media_date = item.find_element(By.CLASS_NAME, 'media__date').text
#                 # print(f'Get news link with title : {title}')
#                 titles.append(title)
#                 sub_titles.append(sub_title)
#                 media_dates.append(media_date)
#                 link_element = item.find_element(By.TAG_NAME, "a")
#                 content_link = link_element.get_attribute("href")
#                 content_links.append(content_link)

# # get detail conten
# authors, detail_contents = [], []
# for link in content_links:
#     print(f'Get detail information from : {link}')
#     driver.get(link)
#     try:
#         WebDriverWait(driver, 15).until(
#             EC.visibility_of_element_located((By.CSS_SELECTOR, "div.container"))
#         )
#         WebDriverWait(driver, 15).until(
#             lambda d: d.execute_script("return document.readyState") == "complete"
#         )
#         author, detail_content = get_author(driver), get_detail_content(driver)
#     except Exception as e:
#         print(e)
#         author, detail_content = '', ''

#     authors.append(author)
#     detail_contents.append(detail_content)

# driver.quit()

# # Summarize Result
# data = summarize_result(titles, sub_titles, media_dates, content_links, authors, detail_contents)

# with open("data.json", "w", encoding="utf-8") as f:
#     json.dump(data, f, ensure_ascii=False, indent=4)


