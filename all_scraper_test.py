from craigslist_scraper import CraigslistScraper
from guru_scraper import GuruScraper
from indeed_scraper import IndeedScraper
from upwork_scraper import UpworkScraper
from simplyhired_scraper import SimplyhiredScraper
from ziprecruiter_scraper import ZipRecruiterScraper


if __name__ == "__main__":
    scrapers = list()
    scrapers.append(CraigslistScraper(base_url="http://baltimore.craigslist.org"))
    scrapers.append(UpworkScraper())
    scrapers.append(GuruScraper())
    scrapers.append(IndeedScraper(location="baltimore"))
    scrapers.append(SimplyhiredScraper(location="Baltimore, MD"))
    scrapers.append(ZipRecruiterScraper(location="baltimore"))
    keys_to_verify = ['source', 'unique_id', 'title', 'date_posted', 'description']
    for scraper in scrapers:
        print scraper.__class__
        for p in scraper.get_postings("computer thing", pages=50):
            for k, v in p.items():
                print k, " => ", v
            for k in keys_to_verify:
                if k not in p:
                    print '%s not there!!' % k
