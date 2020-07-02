import copy
import re
from fuzzysearch import find_near_matches
from unidecode import unidecode
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


def parse_result(rows, keywords=None, text=None, title=None):
    new_item = None
    current_keyword_value = 1
    current_match_value = 4

    for row in map(lambda x: copy.copy(x), rows):
        publication_tag = row.find_all('i')[-1]
        publication_title = publication_tag.text
        publication_tag.clear()

        if keywords:
            value = rate_keywords(keywords, row.text)
            if value < current_keyword_value:
                continue
            current_keyword_value = value

        title_result = titleNHM.search(row.text)
        if title_result:
            parsed_title = title_result.group(1)
        else:
            parsed_title = publication_title

        if text:
            match = find_near_matches(unidecode(parsed_title.lower()), text, max_l_dist=5)
            if len(match) == 0 or match[0].dist > current_match_value:
                continue
            current_match_value = match[0].dist

        if title:
            match = find_near_matches(unidecode(title.lower()), unidecode(parsed_title.lower()), max_l_dist=5)
            if len(match) == 0 or match[0].dist > current_match_value:
                continue
            current_match_value = match[0].dist

        if title_result:
            new_item = zot.item_template('journalArticle')
            new_item['publicationTitle'] = publication_title

            volume_result = volumeIssue.search(row.text)
            if volume_result:
                new_item['volume'] = volume_result.group(1)
                new_item['issue'] = volume_result.group(3)

            pages_result = page.search(row.text)
            if pages_result:
                new_item['pages'] = pages_result.group(1)
        else:
            new_item = zot.item_template('document')

        new_item['title'] = parsed_title

        author_result = authors.search(row.text)
        if author_result:
            for counter, author in enumerate(author_result.group(1).split(";")):
                if re.search(r'et al\.?', author):
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
