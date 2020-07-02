import os
import subprocess
import tkinter as tk
import re
import textract
from langdetect import detect
from tkinter import simpledialog
from pyzotero import zotero
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
# defaultFirstName = 'Jean-Yves'
# defaultLastName = 'Rasplus'
defaultItemType = 'journalArticle'
# defaultLanguage = 'English'

# Variables
collection = 'ZZEZPBPT'

zot = zotero.Zotero(340810, 'group', 'KNAt5LsFJvWquBhywDpNtsv0')

# types = zot.item_types()
# print(types)
#
# fields = zot.item_fields()
# print(fields)
#
# creators = zot.creator_fields()
# print(creators)

items = zot.collection_items(collection, itemType='attachment', start=0)

for item in map(lambda i: i['data'], items):
    if 'parentItem' not in item:
        print(item)

        zot.dump(item['key'], 'original.pdf', './temp')
        os.system('ocrmypdf --pages 1 --force-ocr --deskew ./temp/original.pdf ./temp/ocr.pdf')
        try:
            text = textract.process('./temp/ocr.pdf', method='pdfminer').decode("utf-8")
        except ShellError:
            print("Could not extract text. Skipping item...")
            continue
        languageCode = detect(text)
        text = text.replace('\n', ' ')
        text = re.sub(' +', ' ', text)
        text = unidecode(text.lower())

        newItem = None
        authorYearRows = None
        fileTitle = item['title']
        yearResult = year.search(fileTitle)
        if yearResult:
            titleResult = titlePdf.search(fileTitle, yearResult.end(), len(fileTitle))
            authorResult = authorPdf.search(fileTitle, 0, yearResult.start())

            if authorResult:
                authorName = authorResult.group(1)
                authorYearRows = process_html('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/browseRefs.dsml',
                                    params={'AUTHORqtype': 'contains', 'AUTHOR': authorName,
                                            'YEAR': yearResult.group()})

            if titleResult and authorYearRows:

                newItem = parse_result(authorYearRows, text=text)
                if newItem is None:
                    newItem = parse_result(authorYearRows, keywords=titleResult.group(1))

                if newItem is None and titleResult:
                    speciesGenusResult = speciesGenusPdf.search(fileTitle)
                    if speciesGenusResult:
                        speciesGenusRows = process_html('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/synonyms.dsml',
                                            params={'ValFamTrib': '', 'VALGENUS': speciesGenusResult.group(1),
                                                    'VALSPECIES': speciesGenusResult.group(2)})
                        newItem = parse_result(speciesGenusRows, text=text)
                        if newItem is None:
                            newItem = parse_result(speciesGenusRows, keywords=titleResult.group(1))

        if newItem is None:
            okularProcess = subprocess.Popen(['okular', './temp/ocr.pdf'],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            title = simpledialog.askstring(title="Title",
                                           prompt="Document Title")
            okularProcess.kill()

            if not title:
                print("Skipping item...")
                continue

            title = title.replace('\n', ' ')
            title = re.sub(' +', ' ', title)
            title = title.strip('.,- ')
            if title.isupper():
                title = title.lower().capitalize()
            print(title)

            if authorYearRows:
                newItem = parse_result(authorYearRows, title=title)

            if newItem is None:
                titleRows = process_html('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/keywords.dsml',
                                         params={'index': 'Keywords', 'search': 'references', 'freeText': title})
                newItem = parse_result(titleRows, title=title)

            if newItem is None:
                titleRows = process_html('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/keywords.dsml',
                                 params={'index': 'Keywords', 'search': 'references',
                                         'freeText': title[:len(title) // 2]})
                newItem = parse_result(titleRows, title=title)

        if newItem is None:
            newItem = zot.item_template(defaultItemType)
            # newItem['creators'][0]['firstName'] = defaultFirstName
            # newItem['creators'][0]['lastName'] = defaultLastName
            print('NOT FOUND')

        if not newItem['title']:
            newItem['title'] = title
        newItem['language'] = languageCode

        match = find_near_matches(unidecode(newItem['title'].lower()), text, max_l_dist=3)
        print(match)
        print(newItem)
        if len(match) == 0:
            okularProcess = subprocess.Popen(['okular', './temp/ocr.pdf'],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            print("No match found! continue? (y/N)")
            answer = input()
            okularProcess.kill()
            if answer.lower() != "y":
                print("Skipping item...")
                continue

        if zot.check_items([newItem]):
            result = zot.create_items([newItem])
            newItem = result['successful']['0']
            zot.addto_collection(collection, newItem)
            item.pop('collections')
            item['parentItem'] = newItem['key']
            if zot.check_items([item]):
                result = zot.update_item(item)
