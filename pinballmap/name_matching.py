import re
from collections.abc import Iterable

from pinballmap.constants import MODEL_ENDINGS

punctuation_regex = re.compile(r"\W+")  # any non-alphanumeric characters
spaces_regex = re.compile(r"\s{2,}")  # 2 or more whitespace characters


def score_match(
    query_string: str, machine_data: dict, query_words: Iterable[str]
) -> int:
    """
    Calculates a quality score to sort search results.

    :param query_string: the cleaned search query string
    :param machine_data: dict of the Pinball Map game data
    :param query_words: words in the query string, already split into words
    :return:
    """
    score = 0
    if query_string == machine_data["cleaned_name"]:
        return 150
    if query_string in machine_data["cleaned_name"]:
        score += 2
    g_words = machine_data["cleaned_name"].split()
    last_word = g_words[-1]
    if last_word in MODEL_ENDINGS:
        score -= 2
    for query_word in query_words:
        if query_word == last_word:
            continue
        if query_word in g_words:
            if len(query_word) >= 3:
                score += 5 + len(query_word) * 2
            else:
                score += 1
    return score
