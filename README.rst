Pinball Map API Client
======================

Python client for `Pinball Map API`_.

Special thanks to `Logan Arcade`_ in Chicago, IL for supporting development of this project.

.. _Pinball Map API: http://pinballmap.com/api/v1/docs
.. _Logan Arcade: https://loganarcade.com/

Current version: 0.4.3

`Source on GitHub <https://github.com/eyesee1/python-pinballmap>`_

`pinballmap at Python Package Index (PyPI) <https://pypi.python.org/pypi/pinballmap/>`_

Documentation at `Read the Docs <https://python-pinballmap.readthedocs.io/en/stable/>`_

Installation
------------

.. code:: bash

    $ pip install pinballmap


Quick Start
-----------

.. code:: python

    >>> from pinballmap import PinballMapClient

    >>> c = PinballMapClient(location_id=0, region_name="chicago", authentication_token="...", user_email="email@example.com")

    # Sync your list of machines by providing a complete list of current Pinball Map machine_ids.
    # e.g.:
    >>> c.update_map([1423, 22, 33, 44, 423, 55])

    # look up games by name, results sorted by match quality:
    >>> c.machine_by_name("Game of Thrones (LE)")
    ({'created_at': '2015-10-22T18:55:02.702Z',
      'id': 2442,
      'ipdb_id': None,
      'ipdb_link': '',
      'is_active': None,
      'machine_group_id': 22,
      'manufacturer': 'Stern',
      'name': 'Game of Thrones (LE)',
      'updated_at': '2015-10-22T18:55:02.702Z',
      'year': 2015}, ...)


Command Line Usage
------------------

Limited functionality at this point, but it does a few things.

.. code:: bash

    >>> pinballmap --help

    usage: pinballmap [-h] [-l LOCATION_ID] [-r REGION_NAME] [-i]
                      [-t AUTHENTICATION_TOKEN] [-e USER_EMAIL] [-p USER_PASSWORD]
                      {search,machine_id,machine_ipdb,loc_machines,get_token}
                      [value [value ...]]

    Interact with the Pinball Map API from the command line.

    positional arguments:
      {search,machine_id,machine_ipdb,loc_machines,get_token}
                            search: finds machine data by name; machine_id: finds
                            machine matching id; machine_ipdb: finds machine by
                            IPDB id; loc_machines: list machines at a location
                            get_token: get an auth token for email and password
      value

    optional arguments:
      -h, --help            show this help message and exit
      -l LOCATION_ID, --location LOCATION_ID
      -r REGION_NAME, --region REGION_NAME
                            region name (e.g., chicago)
      -i, --id-only         return only machine ids for query
      -t AUTHENTICATION_TOKEN, --token AUTHENTICATION_TOKEN
                            API authentication token (needed for all write
                            operations)
      -e USER_EMAIL, --email USER_EMAIL
                            API User email address (required for all write
                            operations)
      -p USER_PASSWORD, --passwword USER_PASSWORD
                            API User password (required if you are not providing a
                            token with -t/--token)

    Happy flipping! This is python-pinballmap v0.2.2, supporting Pinball Map API
    v1.0




    >>> pinballmap search 'Game of Thrones (LE)'
    id    name                       manufacturer      year    ipdb_id
    ----  -------------------------  --------------  ------  ---------
    2442  Game of Thrones (LE)       Stern             2015
    2441  Game of Thrones (Pro)      Stern             2015
    2527  Game of Thrones (Premium)  Stern             2015
     760  The Bally Game Show        Bally             1990        985


    >>> pinballmap --location 4495 loc_machines
     id  name                                        manufacturer      year    ipdb_id
   ----  ------------------------------------------  --------------  ------  ---------
   1296  AC/DC (Premium)                             Stern             2012       5775
   2832  Attack From Mars (Remake)                   Chicago Gaming    2017
   2728  Batman 66 (LE)                              Stern             2016       6355
   3022  Deadpool (Pro)                              Stern             2018
    738  Dr. Dude                                    Bally             1990        737
   2442  Game of Thrones (LE)                        Stern             2015       6309
   2571  Ghostbusters (LE)                           Stern             2016       6334
   2875  Guardians of the Galaxy (Pro)               Stern             2017       6474
   2924  Iron Maiden: Legacy of the Beast (Premium)  Stern             2018
    695  Junk Yard                                   Williams          1996       4014
   2353  Kiss                                        Stern             2015       6265
   2306  Medieval Madness (Remake)                   Chicago Gaming    2015       6263
   1606  Metallica (Premium)                         Stern             2013       6030
    641  Monster Bash                                Williams          1998       4441
    723  PIN-BOT                                     Williams          1986       1796
    677  Radical!                                    Bally             1990       1904
   1276  Shaq Attaq                                  Gottlieb          1995       2874
   2565  Spider-Man (Vault Edition)                  Stern             2016       6328
    684  Star Trek: The Next Generation              Williams          1993       2357
    694  Star Wars                                   Data East         1992       2358
   2844  Star Wars (Premium)                         Stern             2017       6429
   1118  TRON: Legacy                                Stern             2011       5682
    779  Taxi                                        Williams          1988       2505
    686  Terminator 2: Judgment Day                  Williams          1991       2524
    687  The Addams Family                           Bally             1992         20
   2203  The Walking Dead (Pro)                      Stern             2014       6155
   2866  Total Nuclear Annihilation                  Spooky            2017       6444
    689  White Water                                 Williams          1993       2768
   2277  Wrestlemania                                Stern             2015       6215


    >>> pinballmap --location 4495 --id-only loc_machines
    1296,2832,2728,3022,738,2442,2571,2875,2924,695,2353,2306,1606,641,723,677,1276,2565,684,694,2844,1118,779,686,687,2203,2866,689,2277



    >>> pinballmap machine_id 2571
     id  name               manufacturer      year    ipdb_id
   ----  -----------------  --------------  ------  ---------
   2571  Ghostbusters (LE)  Stern             2016       6334


Example Django ``settings.py``
------------------------------

NOTE: Django settings, if present, will take precedence over arguments to PinballMapClient(...)

.. code-block:: python

    PINBALL_MAP = {
        'region_name': 'chicago', # a region name to use if not specified in code
        'location_id': your_location_id,  # should be an int
        # email and token are required for all write operations
        'user_email': '...', # your pinball map account email, needed for write operations
        'user_password': '...', # your pinball map password, needed for write operations (not needed with token)
        'authentication_token': '...', # your pinball map api token, needed for write operations
        'cache_name': 'default',  # default: 'default'
        'cache_key_prefix': 'pmap_',  # default: 'pmap_'
    }



Example Django management command
---------------------------------

Create yourapp/management/commands/update_pinball_map.py and use this as a starting point:

.. code-block:: python

   from django.core.management.base import BaseCommand, CommandError
   from pinballmap import PinballMapClient
   from yourapp.somewhere import get_current_game_list


   class Command(BaseCommand):
       help = 'Update the Pinball Map API. Adds/removes machines from our location.'

       def handle(self, *args, **options):
           try:
               games = get_current_game_list()  # ← your code provides a list of current IDs
               # no args needed if you used Django settings as shown above:
               c = PinballMapClient()
               c.update_map([g.pinball_map_id for g in games])
               self.stdout.write(self.style.SUCCESS("Pinball Map updated."))
           except Exception as err:
               self.stderr.write(self.style.ERROR("Could not update pinball map because: {}".format(err)))



Change Log
==========

0.4.3
-----

* updated minimum Python version to 3.11
* changed docs theme from "classic" to ReadTheDocs
* updated some incorrect information
* updated dependencies
* fixed Poetry config so it can install, build, and publish properly


0.3.6
-----

* fixed a bug where code expected the wrong status code
* changed from using ``requirements.txt`` to Poetry for package management
* did a bit of code reorganization


0.3.4
-----
* hopefully fix docs
* fix error from bumpversion


0.3.3
-----

* requires Python 3.6
* CLI catches authentication errors more cleanly
* mostly code cleanups
* help outputs version # of python-pinballmap and Pinball Map API version supported
* all python code is now formatted using `black`_

.. _black: https://black.readthedocs.io/en/stable/



0.2.0
-----

* breaking change: PinballMapClient now takes keyword arguments, old ordered argument syntax will no longer work
* now supports authentication tokens, signup process, getting auth details
* now uses https by default
* fix dry-run bug


0.1.2
-----
* initial release


Roadmap
=======

* update command line interface to support signup and getting auth details
* eventually support all API actions, such as scores, machine conditions, etc.
