from operator import itemgetter
from typing import Dict, Tuple, List, Iterable, Union, Any
import re
import logging

import requests

try:
    from django.conf import settings
    from django.core.cache import caches
except ImportError:
    settings = None
    caches = None

__all__ = ['PinballMapClient', 'VERSION']

VERSION = '0.2.0'
logger = logging.getLogger(__name__)
STRIP_WORDS = ('the', 'and', 'for', 'with', 'a', 'of')
MODEL_ENDINGS = ('le', 'pro', 'premium', 'edition' 'standard')
punctuation_regex = re.compile(r'\W+')  # any non-alphanumeric characters
spaces_regex = re.compile(r'\s{2,}')  # 2 or more whitespace characters


def clean_name(s: str) -> str:
    """
    Cleans up a machine name string for better search matching by removing common words and stripping
    out junk.

    :param s: machine name
    :return: cleaned name
    """
    original = s
    s = punctuation_regex.sub(' ', s).lower()
    for word in STRIP_WORDS:
        pattern = r"\b" + word + r"\b"
        s = re.sub(pattern, ' ', s)
    s = spaces_regex.sub(' ', s).strip()
    # handle unlikely case where the above leaves an empty string:
    if not s:
        # simpler cleaning that doesn't remove any words
        # I mean: whoa, what if somebody names a machine "And For The", or "The The"?
        s = original.lower()
        s = spaces_regex.sub(' ', s).strip()
    return s


def score_match(query_string: str, machine_data: Dict, query_words: Iterable[str]) -> int:
    """
    Calculates a quality score to sort search results.

    :param query_string: the cleaned search query string
    :param machine_data: dict of the Pinball Map game data
    :param query_words: words in the query string, already split into words
    :return:
    """
    score = 0
    if query_string == machine_data['cleaned_name']:
        return 150
    if query_string in machine_data['cleaned_name']:
        score += 2
    g_words = machine_data['cleaned_name'].split()
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


class PinballMapClient:
    """
    Creates a ``PinballMapClient``, optionally locked to a specific location_id and region name.
    It will use Django's default cache if installed and available.

    Passed-in values are optional.

    You can use an instance to look up machines by name or id without specifying a location or region.
    Most other methods will fail without them.

    If Django is installed and is in ``DEBUG`` mode, any write operations to the API will operate as a
    "dry run". This is to prevent you from accidentally updating the map with inaccurate development data.
    (You're welcome.)
    
    :param user_token: Your Pinball Map API Authorization Token, needed for all write operations.
    :param location_id: Your location_id, as found in the Pinball Map data
    :param region_name: Your region name, as found in the Pinball Map data
    :param cache: a cache object with get and set methods compatible with Django's cache
    """

    API_VERSION = "1.0"  # the Pinball Map API version supported
    BASE_URL = "https://pinballmap.com/api/v1"  # no trailing slash!

    def __init__(self, user_email: str = "", user_token: str = "", location_id: int = None, region_name: str = "",
                 cache: Any = None) -> None:
        self.cache = cache
        self.cache_name = 'default'
        self.user_email = user_email
        self.user_token = user_token
        self.cache_key_prefix = 'pmap_'
        self.location_id = location_id
        self.region_name = region_name
        self.dry_run = False
        if settings:
            try:
                self.location_id = int(settings.PINBALL_MAP['location_id'])
                self.region_name = settings.PINBALL_MAP['region_name']
                self.cache_name = settings.PINBALL_MAP.get('cache_name', self.cache_name)
                self.user_email = settings.PINBALL_MAP.get('user_email', self.user_email)
                self.user_token = settings.PINBALL_MAP.get('user_token', self.user_token)
                self.cache_key_prefix = settings.PINBALL_MAP.get('cache_key_prefix', self.cache_key_prefix)
                self.dry_run = True if settings.DEBUG is True else False
            except Exception as exc:
                raise ValueError("Could not use your Django settings because: {}".format(exc))
        if caches:
            self.cache = caches[self.cache_name]
        if location_id:
            self.location_id = location_id
        if region_name:
            self.region_name = region_name
        self.lmxs = []
        self.all_machines = []
        self.session = requests.Session()
        if not self.user_email or not self.user_token:
            logger.warning("Without user_email and user_token, all write operations will fail.")

    def get_all_machines(self) -> List[Dict]:
        """
        Get list of all machines from PM DB. Cached to avoid a zillion large requests.
        Currently we are not storing results in the object because it's unlikely for an instance to be re-used
        for multiple name searches.

        :return: list of every machine
        """
        cache_key = '{}_machines'.format(self.cache_key_prefix)
        if self.cache:
            data = self.cache.get(cache_key, {})
            if data:
                return data
        r = self.session.get("{}/machines.json".format(self.BASE_URL))
        if r.status_code != requests.codes.ok:
            logger.error("Getting list of all pinball map games failed with status code {}".format(r.status_code))
            r.raise_for_status()
        data = r.json()['machines']
        # patch raw data with searchable cleaned names
        for g in data:
            g['cleaned_name'] = clean_name(g['name'])
        if self.cache:
            self.cache.set(cache_key, data, 15 * 60)
        return data

    def get_location_machine_xrefs(self) -> List[Dict]:
        """
        Gets the list of location_machine_xrefs (LMXs) for our region, then filter it to include only ones from
        our location_id.

        Since this API request is massive and slow, and likely to be accessed multiple times in the lifetime on an
        instance (when syncing, for example), we are using two levels of caching here.
        We store the filtered LMXs for our location in the PinballMapClient instance (in-memory),
        and ALSO cache the results for 15 minutes in Django's cache
        (if available). We are assuming no instance of this object will ever live long enough to be
        concerned about needing to bust its own copy of the cached data, but it will benefit from recent previous
        runs.

        :return: list of LMXs for ``location_id``
        """
        if len(self.lmxs) > 0:
            return self.lmxs
        cache_key = "{}_lmxs".format(self.cache_key_prefix)
        if self.cache:
            data = self.cache.get(cache_key, [])
            if data:
                self.lmxs = data
                return data
            del data
        url = "{BASE_URL}/region/{region_name}/location_machine_xrefs.json".format(BASE_URL=self.BASE_URL,
                                                                                   region_name=self.region_name)
        r = self.session.get(url)
        if r.status_code != requests.codes.ok:
            logger.error("Getting list of all pinball map games failed with status code {}".format(r.status_code))
        r.raise_for_status()
        raw_data = r.json()['location_machine_xrefs']
        data = [lmx for lmx in raw_data if int(lmx['location']['id']) == self.location_id]
        del raw_data
        if self.cache:
            self.cache.set(cache_key, data, 15 * 60)
        self.lmxs = data
        return data

    def machine_by_name(self, query_string: str, min_score: int = 2, include_score: bool = False) -> Union[
        Tuple[Dict], Tuple[Tuple[Dict, str]]]:
        """
        Finds likely name matches from the Pinball Map database and sorts results by a match quality score.

        :param query_string: name of the game
        :param min_score: minimum quality score for matches. Our default of 2 seems to be the sweet spot.
        :param include_score: whether to include the match quality scores. Default = ``False``.
        :return: matches
        """
        all_games = self.get_all_machines()
        query_string = clean_name(query_string)
        query_words = tuple(query_string.split())
        results = []  # list of tuples: (game, score)
        set_high_bar = False
        for g in all_games:
            score = score_match(query_string, g, query_words)
            if score >= min_score:
                data = g.copy()
                del data['cleaned_name']
                results.append((data, score))
                if score >= 150:
                    set_high_bar = True
        final_results = tuple(sorted(results, key=itemgetter(1), reverse=True))
        if set_high_bar:
            # if we ever hit a high match score, only include top 5. At that point there is no need to grab at straws.
            final_results = tuple(final_results[:4])
        if include_score:
            return final_results
        return tuple(map(itemgetter(0), final_results))

    def machine_by_ipdb_id(self, ipdb_id: int) -> Union[Dict, None]:
        """
        Find machine by IPDB number

        :param ipdb_id: IPDB ID number
        :return: pinball map data (as dict) or None if no match
        """
        all_games = self.get_all_machines()
        for g in all_games:
            if g['ipdb_id'] == ipdb_id:
                return g
        return None

    def machine_by_map_id(self, map_id: int) -> Union[Dict, None]:
        """
        Find machine by pinball map ID

        :param map_id: pinball map ID number
        :return: pinball map data (as dict) or None if no match
        """
        all_games = self.get_all_machines()
        for g in all_games:
            if g['id'] == map_id:
                return g
        return None

    def machines_at_location(self, location_id: int = None) -> List[Dict]:
        """
        List the machines at location_id

        :param location_id: optional location_id, or it will use the one in settings or set at init
        :return: list of machines matching location_id
        """
        if not location_id:
            location_id = self.location_id
        r = self.session.get(
            "{base}/locations/{id}/machine_details.json".format(base=self.BASE_URL, id=location_id))
        if r.status_code != requests.codes.ok:
            logger.error(
                "Getting list of machines at our location failed with status code {}".format(r.status_code))
        r.raise_for_status()
        return r.json()['machines']

    def compare_location(self, my_machine_ids: Iterable[int]) -> Dict:
        """
        Compares a machine list with Pinball Map's data. Returns a ``dict`` with which ids to
        add, remove, or ignore (meaning they are already listed).

        :param my_machine_ids: iterable of Pinball Map machine_ids
        :return: {'add': [id0, id1, idn...], 'remove': [id0, id1, idn...], 'ignore': [...]}
        """
        my_machine_ids = frozenset(my_machine_ids)
        map_machine_ids = frozenset([g['id'] for g in self.machines_at_location()])
        add = my_machine_ids.difference(map_machine_ids)
        remove = map_machine_ids.difference(my_machine_ids)
        ignore = my_machine_ids.intersection(map_machine_ids)
        return dict(add=add, remove=remove, ignore=ignore)

    def lmx_by_machine_id(self, machine_id: int) -> Dict:
        """
        Get the ``location_machine_xref`` for ``machine_id`` at my location.

        :param machine_id:
        :return: LMX, if found
        """
        lmxs = self.get_location_machine_xrefs()
        for lmx in lmxs:
            if lmx['machine']['id'] == machine_id:
                return lmx
        return {}

    def remove_machine(self, machine_id: int) -> Union[Dict, None]:
        """
        Remove a machine from my location.

        NOTE: If it detects that Django is in debug mode, it will not actually perform the removal.

        :param machine_id: machine id to remove
        :return: JSON result of operation (as a dict) or None
        """
        lmx = self.lmx_by_machine_id(machine_id)
        if not lmx:
            logger.warning(
                "Tried to remove machine_id {} from pinball map, but there was no matching LMX.".format(
                    machine_id))
            return None
        lmx_id = lmx['id']
        url = "{BASE_URL}/location_machine_xrefs/{lmx_id}.json".format(BASE_URL=self.BASE_URL, lmx_id=lmx_id)
        if settings.dry_run:
            logger.warning("since Django is in DEBUG mode, I'm not going to DELETE {}".format(url))
            return None
        params = {'user_email': self.user_email, 'user_token': self.user_token}
        r = self.session.delete(url, params=params)
        if r.status_code != requests.codes.ok:
            logger.error(
                "Failed to remove id {} at URL {} status code={}, content: {}".format(machine_id,
                                                                                      r.url,
                                                                                      r.status_code,
                                                                                      r.content))
        r.raise_for_status()
        result = r.json()
        return result

    def add_machine(self, machine_id: int) -> Union[Dict, None]:
        """
        Add a machine to my location.

        NOTE: If it detects that Django is in debug mode, it will not actually perform the removal.

        :param machine_id:
        :return: JSON result or None.
        """
        url = "{BASE_URL}/location_machine_xrefs.json".format(BASE_URL=self.BASE_URL)
        if settings.dry_run:
            logger.warning("since Django is in DEBUG mode, I'm not going to POST to {}".format(url))
            return None
        params = {'user_email': self.user_email, 'user_token': self.user_token, 'location_id': self.location_id,
                  'machine_id': machine_id}
        r = self.session.post(url, params=params)
        if r.status_code != requests.codes.ok:
            logger.warning(
                "Failed to add id {} to Pinball Map at URL {} :: status code={}, content: {}".format(machine_id, r.url,
                                                                                                     r.status_code,
                                                                                                     r.content))
        r.raise_for_status()
        result = r.json()
        return result

    def update_map(self, machine_ids: Iterable[int]) -> Dict:
        """
        Given a complete list of machine_ids for the location, this will add and remove them as needed so that
        Pinball Map matches your current list of machines.

        :param machine_ids: the pinball map id numbers for your current list of machines
        :return: dict of count of machines added, removed, or ignored
        """
        change_data = self.compare_location(machine_ids)
        errors = {}
        added = []
        removed = []
        for machine_id in change_data['add']:
            try:
                self.add_machine(machine_id)
            except Exception as exc:
                errors[machine_id] = "Failed to add: {}".format(exc)
                continue
            added.append(machine_id)
        for machine_id in change_data['remove']:
            try:
                self.remove_machine(machine_id)
            except Exception as exc:
                errors[machine_id] = "Failed to remove: {}".format(exc)
                continue
            removed.append(machine_id)
        return dict(added=len(added), removed=len(removed), ignored=len(change_data['ignore']), errors=errors,
                    error_count=len(errors))
