from bs4 import BeautifulSoup
import requests


def table_to_row(table):
    return table.find("td")


def process_html(url, params):
    result = requests.get(url, params)
    soup = BeautifulSoup(result.text, 'html.parser')
    tables = soup.find_all("table", {"class": "ucdRefTable"})
    rows = list(map(table_to_row, tables))

    paging = soup.find("td", {"class": "pageTable", "align": "center"})
    if paging:
        links = paging.find_all("a")
        for link in links:
            result = requests.get('https://www.nhm.ac.uk/our-science/data/chalcidoids/database/' + link['href'])
            soup = BeautifulSoup(result.text, 'html.parser')
            tables = soup.find_all("table", {"class": "ucdRefTable"})
            rows = rows + list(map(table_to_row, tables))

    return rows
