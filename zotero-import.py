import requests
import subprocess
import tkinter as tk
import re
import textract
from langdetect import detect
from tkinter import simpledialog
from pyzotero import zotero
from parse_result import parse_result
from fuzzysearch import find_near_matches
from unidecode import unidecode

ROOT = tk.Tk()
ROOT.withdraw()

titlePdf = re.compile(r"(\d{4})[a-z]? (.*)\.")
authorPdf = re.compile(r"([^\d ]*) ")
speciesGenusPdf = re.compile(r"([A-Z ]{1}[a-z]+) ([a-z])+")
year = re.compile(r"\d{4}")

# Default Variables
# defaultFirstName = 'Jean-Yves'
# defaultLastName = 'Rasplus'
defaultItemType = 'journalArticle'
defaultLanguage = 'English'

# Variables
collection = 'TS5VPKBI'

zot = zotero.Zotero(340810, 'group', 'KNAt5LsFJvWquBhywDpNtsv0')

# types = zot.item_types()
# print(types)
#
# fields = zot.item_fields()
# print(fields)
#
# creators = zot.creator_fields()
# print(creators)

items = zot.collection_items(collection, itemType='attachment', start=300)

for item in map(lambda i: i['data'], items):
    if 'parentItem' not in item:
        print(item)

        zot.dump(item['key'], 'original.pdf', './temp')
        ocrProcess = subprocess.Popen(
            ['ocrmypdf', '--force-ocr', '--deskew', '--pages', '1', './temp/original.pdf', './temp/ocr.pdf'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        newItem = None
        fileTitle = item['title']
        yearResult = year.search(fileTitle)
        titleResult = titlePdf.search(fileTitle)
        authorResult = authorPdf.search(fileTitle)
        if yearResult and titleResult and authorResult:
            authorName = authorResult.group(1)

            x = requests.get('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/browseRefs.dsml',
                             params={'AUTHORqtype': 'contains', 'AUTHOR': authorName, 'YEAR': yearResult.group()})

            newItem = parse_result(x.text, titleResult.group(2))

        if newItem is None and titleResult:
            speciesGenusResult = speciesGenusPdf.search(fileTitle)
            if speciesGenusResult:
                x = requests.get('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/synonyms.dsml',
                                 params={'ValFamTrib': '', 'VALGENUS': speciesGenusResult.group(1),
                                         'VALSPECIES': speciesGenusResult.group(2)})
                newItem = parse_result(x.text, titleResult.group(2))

        ocrProcess.wait()
        text = textract.process('./temp/ocr.pdf').decode("utf-8")
        languageCode = detect(text)

        if newItem is None:
            okularProcess = subprocess.Popen(['okular', './temp/ocr.pdf'],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            title = simpledialog.askstring(title="Title",
                                           prompt="Document Title")
            okularProcess.kill()

            title = title.replace('\n', ' ')
            title = re.sub(' +', ' ', title)
            title = title.strip('.,- ')
            if title.isupper():
                title = title.lower().capitalize()
            print(title)

            x = requests.get('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/keywords.dsml',
                             params={'index': 'Keywords', 'search': 'references', 'freeText': title})
            newItem = parse_result(x.text)

            # if newItem is None:
            #     x = requests.get('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/keywords.dsml',
            #                      params={'index': 'Keywords', 'search': 'references',
            #                              'freeText': title[:len(title) // 2]})
            #     newItem = parse_result(x.text)

        if newItem is None:
            newItem = zot.item_template(defaultItemType)
            # newItem['creators'][0]['firstName'] = defaultFirstName
            # newItem['creators'][0]['lastName'] = defaultLastName
            print('NOT FOUND')

        if not newItem['title']:
            newItem['title'] = title

        if languageCode:
            newItem['language'] = languageCode
        else:
            newItem['language'] = defaultLanguage

        text = text.replace('\n', ' ')
        text = re.sub(' +', ' ', text)
        match = find_near_matches(unidecode(newItem['title'].lower()), unidecode(text.lower()), max_l_dist=3)

        print(match)
        print(newItem)
        if len(match) == 0:
            okularProcess = subprocess.Popen(['okular', './temp/ocr.pdf'],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            print("No match found! continue? (y/N)")
            answer = input()
            okularProcess.kill()
            if answer != "y":
                continue

        if zot.check_items([newItem]):
            result = zot.create_items([newItem])
            newItem = result['successful']['0']
            zot.addto_collection(collection, newItem)
            item.pop('collections')
            item['parentItem'] = newItem['key']
            if zot.check_items([item]):
                result = zot.update_item(item)
