import re

from pinballmap.constants import STRIP_WORDS
from pinballmap.name_matching import punctuation_regex, spaces_regex


def clean_name(s: str) -> str:
    """
    Cleans up a machine name string for better search matching by removing common words
    and stripping out junk.

    :param s: machine name
    :return: cleaned name
    """
    original = s
    s = punctuation_regex.sub(" ", s).lower()
    for word in STRIP_WORDS:
        pattern = r"\b" + word + r"\b"
        s = re.sub(pattern, " ", s)
    s = spaces_regex.sub(" ", s).strip()
    # handle unlikely case where the above leaves an empty string:
    if not s:
        # simpler cleaning that doesn't remove any words
        # I mean: whoa, what if somebody names a machine "And For The", or "The The"?
        s = original.lower()
        s = spaces_regex.sub(" ", s).strip()
    return s


def ok_response_code(status_code: int):
    return 200 < status_code < 400
