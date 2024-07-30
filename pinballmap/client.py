import logging
from collections.abc import Iterable
from operator import itemgetter

import requests

from pinballmap.auth import requires_authorization
from pinballmap.exceptions import PinballMapAuthenticationFailure
from pinballmap.name_matching import score_match
from pinballmap.utilities import clean_name, ok_response_code

try:
    from django.conf import settings
    from django.core.cache import caches

except ImportError:
    settings = None
    caches = None

__all__ = ["PinballMapClient"]

logger = logging.getLogger(__name__)


class PinballMapClient:
    """
    Creates a ``PinballMapClient``, optionally locked to a specific location_id and
    region name. It will use Django's default cache if installed and available.

    Passed-in values are optional. Authentication Token and email is needed for all
    write operations.

    You can use an instance to look up machines by name or id without specifying a
    location or region. Most other methods will fail without them.

    If Django is installed and is in ``DEBUG`` mode, any write operations to the API
    will operate as a "dry run". This is to prevent you from accidentally updating the
    map with inaccurate development data. (You're welcome.)

    .. note::

        The API uses names a bit inconsistently… sometimes it's user_token, sometimes
        it's authentication_token. Sometimes username, sometimes login. Always check
        the docs when adding/changing code here.

    :param authentication_token: Your Pinball Map API Authentication Token, needed for
                                 all write operations.
    :param user_email: map account email
    :param user_password: map account password
    :param location_id: Your location_id, as found in the Pinball Map data
    :param region_name: Your region name, as found in the Pinball Map data
    :param cache: a cache object with get and set methods compatible with Django's cache
    :param cache_name: Django cache name to use. Default: 'default'
    :param cache_key_prefix: a prefix for cache keys. Default: 'pmap_'
    """

    API_VERSION = "1.0"  # the Pinball Map API version supported
    BASE_URL = "https://pinballmap.com/api/v1"  # no trailing slash!

    def __init__(self, **kwargs) -> None:
        self.authentication_token = kwargs.get("authentication_token", None)
        self.user_email = kwargs.get("user_email", None)
        self.user_password = kwargs.get("user_password", None)
        self.location_id = kwargs.get("location_id", None)
        self.region_name = kwargs.get("region_name", None)
        self.cache = kwargs.get("cache", None)
        self.cache_name = kwargs.get("cache_name", "default")
        self.cache_key_prefix = kwargs.get("cache_key_prefix", "pmap_")
        self.dry_run = False
        # if Django is present, override with its settings
        if settings:
            try:
                self.location_id = int(settings.PINBALL_MAP["location_id"])
                self.region_name = settings.PINBALL_MAP["region_name"]
                self.cache_name = settings.PINBALL_MAP.get(
                    "cache_name", self.cache_name
                )
                self.user_email = settings.PINBALL_MAP.get(
                    "user_email", self.user_email
                )
                self.user_password = settings.PINBALL_MAP.get(
                    "user_password", self.user_password
                )
                self.authentication_token = settings.PINBALL_MAP.get(
                    "authentication_token", self.authentication_token
                )
                self.cache_key_prefix = settings.PINBALL_MAP.get(
                    "cache_key_prefix", self.cache_key_prefix
                )
                self.dry_run = settings.DEBUG is True

            except Exception as exc:
                raise ValueError(
                    f"Could not use your Django settings for Pinball Map API "
                    f"because: {exc}"
                ) from exc

        if caches:
            self.cache = caches[self.cache_name]

        self.lmxs = []
        self.all_machines = []
        self.session = requests.Session()
        if not self.authentication_token and self.user_email and self.user_password:
            # attempt to get token from email and password, fail quietly so it's
            # possible to try again:
            details = dict()
            try:
                details = self.auth_details(self.user_email, self.user_password)

            except Exception as msg:
                logger.warning(f"PinballMapClient self-authentication failed. {msg}")

            if "authentication_token" in details:
                self.authentication_token = details["authentication_token"]

        if not self.user_email or not self.authentication_token:
            logger.info(
                "Without user_email and authentication_token, all write operations "
                "will fail."
            )

    def get_all_machines(self) -> list[dict]:
        """
        Get list of all machines from PM DB. Cached to avoid a zillion large requests.
        Currently we are not storing results in the object because it's unlikely for an
        instance to be re-used for multiple name searches.

        :return: list of every machine
        """
        cache_key = f"{self.cache_key_prefix}_machines"
        if self.cache:
            data = self.cache.get(cache_key, {})
            if data:
                return data

        r = self.session.get(f"{self.BASE_URL}/machines.json")
        if r.status_code != requests.codes.ok:
            logger.error(
                f"Getting list of all pinball map games failed with status "
                f"code {r.status_code}"
            )
            r.raise_for_status()

        data = r.json()["machines"]

        # patch raw data with searchable cleaned names
        for g in data:
            g["cleaned_name"] = clean_name(g["name"])

        if self.cache:
            self.cache.set(cache_key, data, 15 * 60)

        return data

    def get_location_machine_xrefs(self) -> list[dict]:
        """
        Gets the list of location_machine_xrefs (LMXs) for our region, then filter
        it to include only ones from our location_id.

        Since this API request is massive and slow, and likely to be accessed multiple
        times in the lifetime on an instance (when syncing, for example), we are using
        two levels of caching here. We store the filtered LMXs for our location in the
        PinballMapClient instance (in-memory), and ALSO cache the results for 15 minutes
        in Django's cache (if available). We are assuming no instance of this object
        will ever live long enough to be concerned about needing to bust its own copy
        of the cached data, but it will benefit from recent previous runs.

        :return: list of LMXs for ``location_id``
        """
        if len(self.lmxs) > 0:
            return self.lmxs
        cache_key = f"{self.cache_key_prefix}_lmxs"
        if self.cache:
            data = self.cache.get(cache_key, [])
            if data:
                self.lmxs = data
                return data
            del data
        url = f"{self.BASE_URL}/region/{self.region_name}/location_machine_xrefs.json"
        r = self.session.get(url)
        if r.status_code != requests.codes.ok:
            logger.error(
                f"Getting list of all pinball map games failed with status "
                f"code {r.status_code}"
            )
        r.raise_for_status()
        raw_data = r.json()["location_machine_xrefs"]
        data = [
            lmx for lmx in raw_data if int(lmx["location"]["id"]) == self.location_id
        ]
        del raw_data
        if self.cache:
            self.cache.set(cache_key, data, 15 * 60)
        self.lmxs = data
        return data

    def machine_by_name(
        self, query_string: str, min_score: int = 2, include_score: bool = False
    ) -> tuple[dict] | tuple[tuple[dict, str]]:
        """
        Finds likely name matches from the Pinball Map database and sorts results by a
        match quality score.

        :param query_string: name of the game
        :param min_score: minimum quality score for matches. Our default of 2 seems to be the sweet spot.
        :param include_score: whether to include the match quality scores. Default = ``False``.
        :return: matches
        """  # noqa: E501
        all_games = self.get_all_machines()
        query_string = clean_name(query_string)
        query_words = tuple(query_string.split())
        results = []  # list of tuples: (game, score)
        set_high_bar = False
        for g in all_games:
            score = score_match(query_string, g, query_words)
            if score >= min_score:
                data = g.copy()
                del data["cleaned_name"]
                results.append((data, score))
                if score >= 150:
                    set_high_bar = True

        final_results = tuple(sorted(results, key=itemgetter(1), reverse=True))
        if set_high_bar:
            # if we ever hit a high match score, only include top 5. At that point there
            # is no need to grab at straws.
            final_results = tuple(final_results[:4])

        if include_score:
            return final_results

        return tuple(map(itemgetter(0), final_results))

    def machine_by_ipdb_id(self, ipdb_id: int) -> dict | None:
        """
        Find machine by IPDB number

        :param ipdb_id: IPDB ID number
        :return: pinball map data (as dict) or None if no match
        """
        all_games = self.get_all_machines()
        for g in all_games:
            if g["ipdb_id"] == ipdb_id:
                return g

        return None

    def machine_by_map_id(self, map_id: int) -> dict | None:
        """
        Find machine by pinball map ID

        :param map_id: pinball map ID number
        :return: pinball map data (as dict) or None if no match
        """
        all_games = self.get_all_machines()
        for g in all_games:
            if g["id"] == map_id:
                return g

        return None

    def machines_at_location(self, location_id: int = None) -> list[dict]:
        """
        List the machines at location_id

        :param location_id: optional location_id, or it will use the one in settings or
                            set at init
        :return: list of machines matching location_id
        """
        if not location_id:
            location_id = self.location_id

        if not location_id:
            raise ValueError("Need a location id")

        r = self.session.get(
            f"{self.BASE_URL}/locations/{location_id}/machine_details.json"
        )
        if r.status_code != requests.codes.ok:
            logger.error(
                f"Getting list of machines at our location failed with status "
                f"code {r.status_code}"
            )

        r.raise_for_status()
        return r.json()["machines"]

    def compare_location(self, my_machine_ids: Iterable[int]) -> dict:
        """
        Compares a machine list with Pinball Map's data. Returns a ``dict`` with which
        ids to add, remove, or ignore (meaning they are already listed).

        :param my_machine_ids: iterable of Pinball Map machine_ids
        :return: {'add': [id0, id1, idn...], 'remove': [id0, id1, idn...], 'ignore': [...]}
        """  # noqa: E501
        my_machine_ids = frozenset(my_machine_ids)
        map_machine_ids = frozenset([g["id"] for g in self.machines_at_location()])
        add = my_machine_ids.difference(map_machine_ids)
        remove = map_machine_ids.difference(my_machine_ids)
        ignore = my_machine_ids.intersection(map_machine_ids)
        return dict(add=add, remove=remove, ignore=ignore)

    def lmx_by_machine_id(self, machine_id: int) -> dict:
        """
        Get the ``location_machine_xref`` for ``machine_id`` at my location.

        :param machine_id:
        :return: LMX, if found
        """
        lmxs = self.get_location_machine_xrefs()
        for lmx in lmxs:
            if lmx["machine"]["id"] == machine_id:
                return lmx

        return {}

    @requires_authorization
    def remove_machine(self, machine_id: int) -> dict | None:
        """
        Remove a machine from my location.

        .. note::

            If it detects that Django is in debug mode, it will not actually
            perform the removal.

        :param machine_id: machine id to remove
        :return: JSON result of operation (as a dict) or None
        """
        lmx = self.lmx_by_machine_id(machine_id)
        if not lmx:
            logger.warning(
                f"Tried to remove machine_id {machine_id} from pinball map, but there "
                f"was no matching LMX."
            )
            return None

        lmx_id = lmx["id"]
        url = f"{self.BASE_URL}/location_machine_xrefs/{lmx_id}.json"
        if self.dry_run:
            logger.warning(
                f"since Django is in DEBUG mode, I'm not going to DELETE {url}"
            )
            return None

        params = {
            "user_email": self.user_email,
            "user_token": self.authentication_token,
            "id": lmx_id,
        }
        r = self.session.delete(url, params=params)
        if not ok_response_code(r.status_code):
            logger.error(
                f"Failed to remove id {machine_id} at URL {r.url} "
                f"status code={r.status_code}, content: {r.content}"
            )

        r.raise_for_status()
        result = r.json()
        return result

    @requires_authorization
    def add_machine(self, machine_id: int) -> dict | None:
        """
        Add a machine to my location.

        .. note::
            If it detects that Django is in debug mode, it will not actually perform
            the addition.

        :param machine_id:
        :return: JSON result or None.
        """
        url = f"{self.BASE_URL}/location_machine_xrefs.json"
        if self.dry_run:
            logger.warning(
                f"since Django is in DEBUG mode, I'm not going to POST to {url}"
            )
            return None

        params = dict(
            user_email=self.user_email,
            user_token=self.authentication_token,
            location_id=self.location_id,
            machine_id=machine_id,
        )
        r = self.session.post(url, params=params)
        if not ok_response_code(r.status_code):
            logger.warning(
                f"Failed to add id {machine_id} to Pinball Map at URL {r.url} :: "
                f"status code={r.status_code}, content: {r.content}"
            )

        r.raise_for_status()
        result = r.json()
        return result

    @requires_authorization
    def update_map(self, machine_ids: Iterable[int]) -> dict:
        """
        Given a complete list of machine_ids for the location, this will add and remove
        them as needed so that Pinball Map matches your current list of machines.

        :param machine_ids: the pinball map id numbers for your current list of machines
        :return: dict of count of machines added, removed, or ignored
        """
        change_data = self.compare_location(machine_ids)
        errors = {}
        added = []
        removed = []
        for machine_id in change_data["add"]:
            try:
                self.add_machine(machine_id)

            except Exception as exc:
                errors[machine_id] = f"Failed to add: {exc}"
                continue

            added.append(machine_id)

        for machine_id in change_data["remove"]:
            try:
                self.remove_machine(machine_id)

            except Exception as exc:
                errors[machine_id] = f"Failed to remove: {exc}"
                continue

            removed.append(machine_id)

        return dict(
            added=len(added),
            removed=len(removed),
            ignored=len(change_data["ignore"]),
            errors=errors,
            error_count=len(errors),
        )

    def _update_self(self, data):
        if "errors" in data or "user" not in data:
            return

        user = data["user"]
        self.authentication_token = user["authentication_token"]
        self.user_email = user["email"]

    def signup_user(
        self, username: str, email: str, password: str, update_self: bool = True
    ) -> dict:
        """
        Creates a user account. Note: This is an easy way to get a token to use later.
        If login is successful, optionally set the token for this client.

        If signup fails, attempt to log in and self-update with the same credentials in
        case the reason for failure is simply that the account already exists.


        .. note::
            The API server will send an email with a verification link. You can't do
            anything further until you confirm it.

        Example responses:

        .. code-block::json

            {
                "user": {
                    "id": 1,
                    "username": "my_username",
                    "email": "email@example.com",
                    "authentication_token": "..."
                }
            }


        .. code-block: json

            {
                "errors": "your entered passwords do not match"
            }


        :param username: the username
        :param email: user's email address
        :param password: the password
        :param update_self: whether to update this client instance's
                            authentication_token, default is True
        :return: result of auth_details request as dict
        """
        params = dict(
            username=username, email=email, password=password, confirm_password=password
        )
        url = f"{self.BASE_URL}/users/signup.json"
        r = self.session.post(url, params=params)
        if not ok_response_code(r.status_code):
            logger.warning(
                f"Failed to create Pinball Map user account for {username}. "
                f"status code={r.status_code}, content={r.content}"
            )
            r.raise_for_status()

        result = r.json()
        if "errors" in result:
            logger.error(
                "Failed to create Pinball Map API account for {}: {}".format(
                    username, str(result["errors"])
                )
            )
            # be persistent in case account exists by trying to log in anyway:
            try:
                return self.auth_details(email, password, update_self=update_self)

            except PinballMapAuthenticationFailure:
                logger.error(
                    f"Could neither create nor log into Pinball Map account {email}"
                )
                raise

        if update_self:
            self._update_self(result)

        return result

    def auth_details(
        self, username: str = None, password: str = None, update_self: bool = True
    ) -> dict:
        """
        Gets the authorization details for user.
        If login is successful, optionally set the token for this client
        (default is True).

        If we have settings in Django, we'll use those automatically if username and
        password are None.

        Example responses:
        ------------------

        .. code-block:: json
        
            {
                "errors": "User is not yet confirmed. Please follow emailed confirmation instructions."
            }


        .. code-block:: json
        
            {
                "user": {
                    "id": 1,
                    "username": "my_username",
                    "email": "email@example.com",
                    "authentication_token": "..."
                }
            }


        :param username: the username or email address
        :param password: the password
        :param update_self: whether to update this client instance's
                            authentication_token, default is True
        :return: result of auth_details request as dict
        """  # noqa: E501
        if username is None and password is None:
            raise ValueError("username and password required")
        params = dict(login=username, password=password)
        url = f"{self.BASE_URL}/users/auth_details.json"
        r = self.session.get(url, params=params)
        if r.status_code != requests.codes.ok:
            logger.warning(
                f"Failed to get Pinball Map auth details for username: {username}. "
                f"status code={r.status_code}, content={r.content}"
            )
            r.raise_for_status()

        result = r.json()
        if "errors" in result:
            logger.error(
                f"username {username} failed to authenticate to Pinball Map API"
            )
            raise PinballMapAuthenticationFailure(str(result["errors"]))

        if update_self:
            self._update_self(result)

        return result
