import re
import csv
import time
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pytz import timezone
from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dateutil.parser import parse
from newspaper import Article
import logging

logging.basicConfig(level=logging.DEBUG, filename='news.log', format='%(asctime)s %(levelname)s:%(message)s')


class NewspaperScraper:
    def __init__(self, newspaper, company, searchTerm, dateStart, dateEnd):
        self.newspaper = newspaper
        self.searchTerm = searchTerm
        self.company = company
        self.dateStart = parse(dateStart)
        self.dateEnd = parse(dateEnd)
        self.links = []

    def get_newspaper_name(self):
        return self.newspaper

    def check_dates(self, date):
        page_date = parse(date.replace("ET", ""))
        if self.dateStart <= page_date <= self.dateEnd:
            return True
        return False

    def newspaper_parser(self, sleep_time=3):
        results = []
        for l in self.links:
            article = Article(url=l)
            try:
                article.download()
                article.parse()
                article.nlp()
            except Exception as e:
                logging.error("issue bundling {} for {}, {}".format(l, self.searchTerm, e))
                time.sleep(20)
                continue
            data = {
                'title': article.title,
                'date_published': article.publish_date,
                'news_outlet': self.newspaper,
                'authors': article.authors,
                'feature_img': article.top_image,
                'article_link': article.canonical_link,
                'keywords': article.keywords,
                'movies': article.movies,
                'summary': article.summary,
                'text': article.text,
                'html': article.html,
                'company': self.company
            }
            results.append(data)
            time.sleep(sleep_time)
        return results

    def write_to_csv(self, data, file_name):
        print('writing to CSV...')

        keys = list(data[0].keys())
        with open(file_name, 'w', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, keys, delimiter='|')
            dict_writer.writeheader()
            dict_writer.writerows(data)

    def write_to_mongo(self, data, collection):
        print('writing to mongoDB...')
        count = 0

        for d in data:
            collection.insert(d)
            count += 1

    def write_to_json(self, data, filename):
        with open(filename, 'w') as fp:
            json.dump(data, fp)


class NewspaperScraperWithAuthentication(NewspaperScraper):
    def __init__(self, newspaper, company, searchTerm, dateStart, dateEnd, userID, password):
        NewspaperScraper.__init__(self, newspaper, company, searchTerm, dateStart, dateEnd)
        self.userId = userID
        self.password = password

        if newspaper == 'Wall Street Journal':
            self.credentials = {
                'username': userID,
                'password': password
            }
            self.login_url = 'https://id.wsj.com/access/pages/wsj/us/signin.html'
            self.submit_id = 'basic-login-submit'

    def newspaper_parser(self, sleep_time=2):
        logging.debug('running newspaper_parser() for secure sites...')

        # Create secure session: login, click the login button
        browser = webdriver.Firefox(executable_path=r'gecko\geckodriver.exe')
        credential_names = list(self.credentials.keys())
        browser.get(self.login_url)
        cred1 = browser.find_element_by_id(credential_names[0])
        cred2 = browser.find_element_by_id(credential_names[1])
        cred1.send_keys(self.credentials[credential_names[0]])
        cred2.send_keys(self.credentials[credential_names[1]])
        time.sleep(10)
        browser.find_element_by_class_name(self.submit_id).click()
        time.sleep(10)
        cookies = browser.get_cookies()
        browser.close()

        s = requests.Session()
        for cookie in cookies:
            s.cookies.set(cookie['name'], cookie['value'])

        results = []
        for l in self.links:
            try:
                page = s.get(l)
            except Exception as e:
                logging.error("issue bundling {} for {}, {}".format(l, self.searchTerm, e))
                print(e)
                time.sleep(20)
                continue

            soup = BeautifulSoup(page.content, features="lxml")
            article = Article(url=l)
            article.set_html(str(soup))
            article.parse()
            article.nlp()
            up_date = article.publish_date
            # we need to find pub and update date of the article
            if self.newspaper == 'Wall Street Journal':
                soup = BeautifulSoup(article.html, features="lxml")
                try:
                    pub_date = soup.find("meta", {"name": "article.published"}).get("content", None)
                    up_date = soup.find("meta", {"name": "article.updated"}).get("content", None)
                    article.publish_date = pub_date
                except Exception as e:
                    logging.error("no date found {} for {}, {}".format(l, self.searchTerm, e))

            data = {
                'search': self.searchTerm,
                'title': article.title,
                'date_published': article.publish_date,
                'date_updated': up_date,
                'news_outlet': self.newspaper,
                'authors': article.authors,
                'article_link': article.canonical_link,
                'keywords': article.keywords,
                'summary': article.summary,
                'text': article.text,
                'html': article.html,
                'company': self.company
            }
            results.append(data)
            time.sleep(sleep_time)

        logging.debug("done for {}, {} parsed".format(self.searchTerm, len(results))
        return results


class WSJScraper(NewspaperScraperWithAuthentication):
    # get links to articles from search, sleep time is sleep between every page
    def get_pages(self, sleep_time=2):
        logging.debug("running get_pages()...  to harvest links")
        links = []
        stop = False
        # search page indexing
        index = 1
        # if there are links on the page
        while not stop:
            # move to next page
            page = requests.get('http://www.wsj.com/search/term.html?KEYWORDS='
                                + self.searchTerm
                                + '&min-date=' + str(self.dateStart.date()).replace('-', '/')
                                + '&max-date=' + str(self.dateEnd.date()).replace('-', '/')
                                + '&page=' + str(index)
                                + '&isAdvanced=true&daysback=4y&andor=AND&sort=date-desc&source=wsjarticle,wsjblogs,sitesearch')
            soup = BeautifulSoup(page.content, features="lxml")
            # if no articles, stop
            if soup.find('div', class_="headline-item") is None:
                stop = True
                logging.debug("no headline found for {} after {} pages".format(self.searchTerm, index))
                continue
                # if articles, for every article in search:
            for result in soup.find_all('div', class_="headline-item"):
                pub_date = result.find('time', class_='date-stamp-container').get_text()
                # check if date is within range, if it is, extract links
                if self.check_dates(pub_date):
                    link = result.find('h3', class_="headline")
                    ltext = link.find('a').get('href')
                    # repair mangled links
                    if 'http://' not in ltext:
                        ltext = 'http://www.wsj.com' + ltext
                    if "http://www.wsj.comhttps://www.wsj.com/" in ltext:
                        ltext = ltext.replace('http://www.wsj.comhttps://www.wsj.com/', 'http://www.wsj.com/')
                    if ltext not in links and 'video' not in ltext:
                        links.append(ltext)
            index += 1
            time.sleep(sleep_time)

        self.links = links
        logging.debug("{} found for  {}".format(len(links), self.searchTerm))
        return links
