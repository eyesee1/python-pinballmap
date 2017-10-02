import argparse
from typing import Dict, Iterable

from tabulate import tabulate

from .client import PinballMapClient, VERSION


def result_table(machines: Iterable[Dict]) -> str:
    table = [['id', 'name', 'manufacturer', 'year', 'ipdb_id']]
    for g in machines:
        table.append([g['id'], g['name'], g['manufacturer'], g['year'], g['ipdb_id']])
    return tabulate(table, headers='firstrow')


def main():
    parser = argparse.ArgumentParser(description="Interact with Pinball Map API",
                                     prog='pinballmap',
                                     epilog="Happy flipping!",
                                     )
    parser.add_argument("-l", "--location", type=int, dest='location_id', default=None)
    parser.add_argument("-r", "--region", help="region name (e.g., chicago)", type=str, dest='region_name',
                        default=None)
    parser.add_argument("-i", "--id-only", action='store_true', help="return only machine ids for query")
    parser.add_argument("-t", "--token", help="API authentication token (needed for all write operations)",
                        type=str, dest="authentication_token", default=None)
    parser.add_argument("-e", "--email", help="User email address (needed for all write operations)", type=str,
                        dest="user_email", default=None)
    parser.add_argument("command", choices=['search', 'machine_id', 'machine_ipdb', 'loc_machines'],
                        help="search: finds machine data by name; "
                             "machine_id: finds machine matching id; "
                             "machine_ipdb: finds machine by IPDB id; "
                             "loc_machines: list machines at a location ")
    parser.add_argument("value", default=None, nargs='*')

    args = parser.parse_args()
    c = PinballMapClient(location_id=args.location_id, region_name=args.region_name,
                         authentication_token=args.authentication_token, user_email=args.user_email)
    if args.command == 'search':
        if len(args.value) == 0:
            parser.error("Query value required.")
        if len(args.value) > 1:
            parser.error("Try putting your search query in quotes.")
        results = c.machine_by_name(args.value[0])
        if len(results) == 0:
            print("No matches.")
        else:
            print(result_table(results))
        return
    if args.command == 'machine_id':
        result = c.machine_by_map_id(int(args.value[0]))
        if not result:
            print("No match.")
        else:
            print(result_table([result]))
        return
    if args.command == 'machine_ipdb':
        result = c.machine_by_ipdb_id(int(args.value[0]))
        if not result:
            print("No match.")
        else:
            print(result_table([result]))
        return
    if args.command == 'loc_machines':
        if not args.location_id:
            parser.error("location id required to list machines at a location.")
        results = c.machines_at_location(args.location_id)
        if args.id_only:
            print(",".join([str(m['id']) for m in results]))
        else:
            print(result_table(results))
