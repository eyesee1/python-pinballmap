Pinball Map API Client
======================

Python client for `Pinball Map API`_.

Special thanks to `Logan Arcade`_ in Chicago for supporting development of this project.

.. _Pinball Map API: http://pinballmap.com/
.. _Logan Arcade: https://loganarcade.com/

Installation
------------

.. code:: bash

    $ pip install python-pinballmap


Quick Start
-----------

.. code:: python

    >>> from pinballmap import PinballMapClient

    >>> c = PinballMapClient(location_id=0, region_name="chicago")

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
                      {search,machine_id,machine_ipdb,loc_machines}
                      [value [value ...]]

    Interact with Pinball Map API

    positional arguments:
      {search,machine_id,machine_ipdb,loc_machines}
                            search: finds machine data by name; machine_id: finds
                            machine matching id; machine_ipdb: finds machine by
                            IPDB id; loc_machines: list machines at a location
      value

    optional arguments:
      -h, --help            show this help message and exit
      -l LOCATION_ID, --location LOCATION_ID
      -r REGION_NAME, --region REGION_NAME
                            region name (e.g., chicago)
      -i, --id-only         return only machine ids for query

    Happy flipping!

    >>> pinballmap search 'Game of Thrones (LE)'
    id    name                       manufacturer      year    ipdb_id
    ----  -------------------------  --------------  ------  ---------
    2442  Game of Thrones (LE)       Stern             2015
    2441  Game of Thrones (Pro)      Stern             2015
    2527  Game of Thrones (Premium)  Stern             2015
     760  The Bally Game Show        Bally             1990        985

    >>> pinballmap --location 4495 loc_machines
      id  name                            manufacturer      year    ipdb_id
    ----  ------------------------------  --------------  ------  ---------
    2728  Batman 66 (LE)                  Stern             2016
     655  Black Knight 2000               Williams          1989        311
     738  Dr. Dude                        Bally             1990        737
     656  Elvira and the Party Monsters   Bally             1989        782
     852  Galaxy                          Stern             1980        980
    2442  Game of Thrones (LE)            Stern             2015
    2571  Ghostbusters (LE)               Stern             2016
    1195  Hercules                        Atari             1979       1155
    2353  Kiss (Stern)                                      2015       6265
     641  Monster Bash                    Williams          1998       4441
     744  Mousin' Around!                 Bally             1989       1635
    2532  Mustang (Premium)               Stern             2014
     723  PIN-BOT                         Williams          1986       1796
    2726  Pabst Can Crusher               Stern             2016
     677  Radical!                        Bally             1990       1904
     678  Revenge from Mars               Bally             1999       4446
     692  Ripley's Believe It or Not!     Stern             2003       4917
    1276  Shaq Attaq                      Gottlieb          1995       2874
    2165  Star Trek (Pro)                 Stern             2013       6044
     684  Star Trek: The Next Generation  Williams          1993       2357
     694  Star Wars                       Data East         1992       2358
    1118  TRON: Legacy                    Stern             2011       5682
     779  Taxi                            Williams          1988       2505
     687  The Addams Family               Bally             1992         20
    2203  The Walking Dead (Pro)          Stern             2014       6155
     689  White Water                     Williams          1993       2768
    2324  Whoa Nellie! Big Juicy Melons   Stern             2015       6252
    2277  Wrestlemania                    Stern             2015

    >>> pinballmap --location 4495 --id-only loc_machines
    2728,655,738,656,852,2442,2571,1195,2353,641,744,2532,723,2726,677,678,692,1276,2165,684,694,1118,779,687,2203,689,2324,2277

    >>> pinballmap machine_id 2571
      id  name               manufacturer      year  ipdb_id
    ----  -----------------  --------------  ------  ---------
    2571  Ghostbusters (LE)  Stern             2016


Example Django ``settings.py``
------------------------------

.. code-block:: python
   :emphasize-lines: 4,5

    PINBALL_MAP = {
        'region_name': 'chicago',
        'location_id': your_location_id,  # should be an int
        'user_email': '...', # your pinball map account email, needed for write operations
        'user_token': '...', # your pinball map api token, needed for write operations
        'cache_name': 'default',  # default: 'default'
        'cache_key_prefix': 'pmap_',  # default: 'pmap_'
    }



Example Django management command
---------------------------------

Create ``yourapp/management/commands/update_pinball_map.py`` and use this as a starting point:

.. code-block:: python
   :emphasize-lines: 11

   from django.core.management.base import BaseCommand, CommandError
   from pinballmap import PinballMapClient
   from yourapp.somewhere import get_current_game_list


   class Command(BaseCommand):
       help = 'Update the Pinball Map API. Adds/removes machines from our location.'

       def handle(self, *args, **options):
           try:
               games = get_current_game_list()  # ← your code provides a list of current IDs
               c = PinballMapConnection()
               c.update_map([g.pinball_map_id for g in games])
               self.stdout.write(self.style.SUCCESS("Pinball Map updated."))
           except Exception as err:
               self.stderr.write(self.style.ERROR("Could not update pinball map because: {}".format(err)))



Changes
=======

0.2.0
-----

* supports authentication tokens
* uses https by default


Roadmap
=======

* read/write machine condition reports
* read/write high scores
* make syncing more resilient by allowing change requests to fail, and recording and returning a list of the
  errors. This allows the rest of a sync operation to continue even if there are errors on a specific add or
  remove operation.
