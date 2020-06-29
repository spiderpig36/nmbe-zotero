import re
from bs4 import BeautifulSoup
from rate_keywords import rate_keywords
from pyzotero import zotero

zot = zotero.Zotero(340810, 'group', 'KNAt5LsFJvWquBhywDpNtsv0')

montDict = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}

date = re.compile(r"\((\d{1,2}) ([A-Z][a-z]*) (\d{4})\)")
year = re.compile(r"\d{4}")
volumeIssue = re.compile(r"(\d+)(\((\d+-?(\d+)?)\))?\:")
page = re.compile(r":(\d+-?(\d+)?)")
authors = re.compile(r"(\D*)\d{4}")
titleNHM = re.compile(r"\d{4}\)?, (.*)\.")


def parse_result(html, keywords=None):
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all("table", {"class": "ucdRefTable"})

    if tables:
        new_item = None
        current_value = 1

        for table in tables:
            row = table.find("td")
            if keywords:
                value = rate_keywords(keywords, row.text)
                if value < current_value:
                    continue
                current_value = value

            if re.search('private publication', row.text, re.IGNORECASE):
                new_item = zot.item_template('document')
            else:
                new_item = zot.item_template('journalArticle')
                new_item['publicationTitle'] = row.find_all('i')[-1].text

                volume_result = volumeIssue.search(row.text)
                if volume_result:
                    new_item['volume'] = volume_result.group(1)
                    new_item['issue'] = volume_result.group(3)

                pages_result = page.search(row.text)
                if pages_result:
                    new_item['pages'] = pages_result.group(1)

            title_result = titleNHM.search(row.text)
            if title_result:
                new_item['title'] = title_result.group(1)

            author_result = authors.search(row.text)
            if author_result:
                for counter, author in enumerate(author_result.group(1).split(";")):
                    if re.search('et al.', author):
                        continue
                    parts = author.split(",")
                    if len(new_item['creators']) < counter + 1:
                        new_item['creators'].append({"creatorType": "author"})
                    new_item['creators'][counter]['lastName'] = parts[0].rstrip()
                    if len(parts) == 2:
                        new_item['creators'][counter]['firstName'] = parts[1].rstrip()
                    else:
                        new_item['creators'][counter]['firstName'] = ''

            year_result = year.search(row.text)
            date_result = date.search(row.text)
            if date_result:
                new_item['date'] = date_result.group(3) + '/' + montDict[
                    date_result.group(2)] + '/' + date_result.group(1)
            elif year_result:
                new_item['date'] = year_result.group()

        return new_item
    return None
