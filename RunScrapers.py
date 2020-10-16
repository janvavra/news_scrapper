import sys
from pymongo import MongoClient
from NewspaperScraper import *

# mongo db settings
client = MongoClient('localhost', 27017)
db = client.News_database


def divide_chunks(l, n):
    """ Divides iterator l to n sized chunks """
    for i in range(0, len(l), n):
        yield l[i:i + n]


def run_scraper(scraper):
    # get a list of all links to news articles
    scraper.get_pages()
    if len(scraper.links) == 0:
        print("0 links found for the search")
        return

    split_links = divide_chunks(scraper.links, 50)
    for l in split_links:
        scraper.links = l
        # scrape data link by link (open them)
        data = scraper.newspaper_parser()
        # write to Mongo in db named db."DB_NAME")
        scraper.write_to_mongo(data, db.fortune1000)


def initialize_scraper(args):
    if args[1] == 'Wall Street Journal':
        run_scraper(WSJScraper(args[1], args[2], args[3], args[4], args[5], args[6], args[7]))


if __name__ == "__main__":
    initialize_scraper(sys.argv)
