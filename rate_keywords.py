import re


def rate_keywords(keywords, text):
    count = 0
    for word in filter(lambda i: len(i) > 1, keywords.split()):
        if re.search(word, text, re.IGNORECASE):
            count += 1

    return count
