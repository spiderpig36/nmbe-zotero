import re


def rate_keywords(keywords, text):
    count = 0
    for word in keywords.split():
        if re.search(word, text, re.IGNORECASE):
            count += 1

    return count
