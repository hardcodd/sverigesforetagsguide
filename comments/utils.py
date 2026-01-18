import os

from django.conf import settings


def check_for_bad_words(comment: str):
    with open(os.path.join(settings.BASE_DIR, 'comments/blacklist.txt'), 'r') as file:

        for w in file:
            w = w.strip()
            if comment.find(w) != -1:
                return True

    return False
