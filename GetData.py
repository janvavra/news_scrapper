from RunScrapers import initialize_scraper
import csv

# settings
number_of_companies = 50
start_companies = 0
# format month-day-year
date_ranges = [
    ["12-31-2019", "01-01-2017"],
    ["12-31-2016", "01-01-2014"],
]

companies = []
with open('fortune50.csv') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    row_count = 0
    for row in csv_reader:
        if row_count < number_of_companies:
            if row_count >= start_companies:
                companies.append([row[2], row[3]])
        row_count += 1

for c in companies:
    ceo = c[1]
    company = c[0]
    for d in date_ranges:
        date_min = d[1]
        date_max = d[0]
        initialize_scraper(
            [0, "Wall Street Journal", company, ceo, date_min, date_max, "UserName", "PassWord"])
