import json
import os
import subprocess
import tkinter as tk
import re
import textract
from crossref_commons.iteration import iterate_publications_as_json
from langdetect import detect
from tkinter import simpledialog
from pyzotero import zotero
from pyzotero.zotero_errors import ResourceNotFound
from textract.exceptions import ShellError
from fuzzysearch import find_near_matches
from unidecode import unidecode
from process_html import process_html
from parse_result import parse_result

ROOT = tk.Tk()
ROOT.withdraw()

titlePdf = re.compile(r"[a-z]? (.*)\.")
authorPdf = re.compile(r"([^\d ]+)")
speciesGenusPdf = re.compile(r"[a-z]? ([A-Z ]{1}[a-z]+) ([a-z]+)")
year = re.compile(r"\d{4}")

# Default Variables
defaultItemType = 'journalArticle'

# Variables
collectionId = 'AACFPRMA'
pdfApp = 'okular'

zot = zotero.Zotero(340810, 'group', 'KNAt5LsFJvWquBhywDpNtsv0')
collections = zot.all_collections(collectionId)

skippedItems = []


# Save skipped items to file
def skipp_item(item):
    print("Skipping item...")
    skippedItems.append(item)
    with open('./temp/skipped_items.json', 'w') as outfile:
        json.dump(skippedItems, outfile, sort_keys=True, indent=4)


# loop over all collections that are sub-collections of the root
for collection in collections:
    print('Collection: ' + collection['data']['name'])
    skip = 0
    # retrieve all items of the collection
    while True:
        # only 50 items can be retrieved with one request. Therefore we repeat this until we do not find new items
        items = zot.collection_items(collection['key'], itemType='attachment', start=skip)
        if len(items) == 0:
            break

        # loop over the batch of items retrieved. We are only interested in the 'data' part of the item
        for item in map(lambda i: i['data'], items):
            # We only process items that do not have a parentItem yet
            if 'parentItem' not in item:
                print(item)
                newItem = None
                authorYearRows = None
                languageCode = None
                text = None
                try:
                    # try to download the file. Skip the item if the download is not possible
                    zot.dump(item['key'], 'original.pdf', './temp')
                except ResourceNotFound:
                    skipp_item(item)
                    continue

                # run ocr over the pdf, we only process the first page
                os.system('ocrmypdf --pages 1 --force-ocr --deskew ./temp/original.pdf ./temp/ocr.pdf')
                try:
                    # read the text of the pdf
                    text = textract.process('./temp/ocr.pdf', method='pdfminer').decode("utf-8")
                    # try to guess the language of the document
                    languageCode = detect(text)
                    # remove line breaks
                    text = text.replace('\n', ' ')
                    # remove duplicate spaces
                    text = re.sub(' +', ' ', text)
                    # convert to lower case and convert to ascii
                    text = unidecode(text.lower())
                except ShellError:
                    print("Could not extract text")

                fileTitle = item['title']
                # get information from the file title with the help of regular expressions
                yearResult = year.search(fileTitle)
                if yearResult:
                    titleResult = titlePdf.search(fileTitle, yearResult.end(), len(fileTitle))
                    authorResult = authorPdf.search(fileTitle, 0, yearResult.start())

                    if authorResult:
                        authorName = authorResult.group(1)
                        # search with the author name and release year
                        authorYearRows = process_html(
                            'https://www.nhm.ac.uk/our-science/data/chalcidoids/database/browseRefs.dsml',
                            params={'AUTHORqtype': 'contains', 'AUTHOR': authorName,
                                    'YEAR': yearResult.group()})

                    if titleResult and authorYearRows:

                        if text:
                            # try to match the search result with the pdf text
                            newItem = parse_result(authorYearRows, text=text)
                        if newItem is None:
                            # try to match the search result with the pdf title keywords
                            newItem = parse_result(authorYearRows, keywords=titleResult.group(1))

                        if newItem is None and titleResult:
                            speciesGenusResult = speciesGenusPdf.search(fileTitle)
                            if speciesGenusResult:
                                # search with the species and genus names
                                speciesGenusRows = process_html(
                                    'https://www.nhm.ac.uk/our-science/data/chalcidoids/database/synonyms.dsml',
                                    params={'ValFamTrib': '', 'VALGENUS': speciesGenusResult.group(1),
                                            'VALSPECIES': speciesGenusResult.group(2)})
                                if text:
                                    # try to match the search result with the pdf text
                                    newItem = parse_result(speciesGenusRows, text=text)
                                if newItem is None:
                                    # try to match the search result with the pdf title keywords
                                    newItem = parse_result(speciesGenusRows, keywords=titleResult.group(1))

                if newItem is None:
                    # display the pdf
                    displayPdfProcess = subprocess.Popen([pdfApp, './temp/ocr.pdf'],
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.PIPE)
                    # let the user input the title of the pdf
                    title = simpledialog.askstring(title="Title",
                                                   prompt="Document Title")
                    # close the pdf
                    displayPdfProcess.kill()

                    if not title:
                        skipp_item(item)
                        continue

                    # make a reasonable title with no line breaks and more or less correct capitalisation
                    title = title.replace('\n', ' ')
                    title = re.sub(' +', ' ', title)
                    title = title.strip('.,- ')
                    if title.isupper():
                        title = title.lower().capitalize()
                    print(title)

                    # queries = {'query.bibliographic': title, 'sort': 'score'}
                    # for result in iterate_publications_as_json(max_results=10, queries=queries):
                    #     match = find_near_matches(result['title'][0].lower(), title.lower(), max_l_dist=3)
                    #     if len(match) > 0:
                    #         newItem = zot.item_template('journalArticle')
                    #         newItem['title'] = result['title'][0]
                    #         if 'volume' in result:
                    #             newItem['volume'] = result['volume']
                    #         if 'issue' in result:
                    #             newItem['issue'] = result['issue']
                    #         if 'page' in result:
                    #             newItem['pages'] = result['page']
                    #         if 'language' in result:
                    #             newItem['language'] = result['language']
                    #         if 'url' in result:
                    #             newItem['url'] = result['URL']
                    #         if 'DOI' in result:
                    #             newItem['DOI'] = result['DOI']
                    #         if 'container-title' in result:
                    #             newItem['publicationTitle'] = result['container-title'][0]
                    #         if 'short-container-title' in result:
                    #             newItem['journalAbbreviation'] = result['short-container-title'][0]
                    #         newItem['date'] = '/'.join(str(x) for x in result['issued']['date-parts'][0])
                    #         if 'author' in result:
                    #             for counter, author in enumerate(result['author']):
                    #                 if len(newItem['creators']) < counter + 1:
                    #                     newItem['creators'].append({"creatorType": "author"})
                    #                 newItem['creators'][counter]['lastName'] = author['family']
                    #                 newItem['creators'][counter]['firstName'] = author['given']
                    #
                    #         break

                    if authorYearRows:
                        newItem = parse_result(authorYearRows, title=title)

                    if newItem is None:
                        # search with the provided title
                        titleRows = process_html(
                            'https://www.nhm.ac.uk/our-science/data/chalcidoids/database/keywords.dsml',
                            params={'index': 'Keywords', 'search': 'references', 'freeText': title})
                        # try to match the search result with the provided title
                        newItem = parse_result(titleRows, title=title)

                    if newItem is None:
                        # search with the first half of the priveded title
                        titleRows = process_html(
                            'https://www.nhm.ac.uk/our-science/data/chalcidoids/database/keywords.dsml',
                            params={'index': 'Keywords', 'search': 'references',
                                    'freeText': title[:len(title) // 2]})
                        # try to match the search result with the provided title
                        newItem = parse_result(titleRows, title=title)

                if newItem is None:
                    # if nothing was found, create an empty item
                    newItem = zot.item_template(defaultItemType)
                    print('NOT FOUND')

                if not newItem['title']:
                    newItem['title'] = title
                if languageCode and not newItem['language']:
                    newItem['language'] = languageCode

                # sanity check: Try to find the resulting title within the pdf.
                # It this succeeds it is very likely that the correct item was found.
                match = []
                if text:
                    match = find_near_matches(unidecode(newItem['title'].lower()), text, max_l_dist=3)
                    print(match)
                print(newItem)
                if len(match) == 0:
                    # of the sanity check did not succeeded we display the pdf again
                    displayPdfProcess = subprocess.Popen([pdfApp, './temp/original.pdf'],
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.PIPE)
                    # let the user decide if the item should be saved
                    print("No match found! continue? (y/N)")
                    answer = input()
                    displayPdfProcess.kill()
                    if answer.lower() != "y":
                        skipp_item(item)
                        continue

                # save the item to zotero
                if zot.check_items([newItem]):
                    result = zot.create_items([newItem])
                    newItem = result['successful']['0']
                    zot.addto_collection(collection['key'], newItem)
                    item.pop('collections')
                    item['parentItem'] = newItem['key']
                    if zot.check_items([item]):
                        result = zot.update_item(item)

        skip += 100
