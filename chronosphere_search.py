import argparse
import json
import sys
import os
import traceback
import urllib.request
import urllib.parse


def parse_args():
    parser = argparse.ArgumentParser()
    # optional argument
    parser.add_argument("text", metavar='text', type=str, nargs='*',
                        help="Search text")
    parser.add_argument("--url", dest="domain",
                        help="Chronosphere URL. E.g. https://custom.chronosphere.io")
    parser.add_argument("--token",
                        help="Auth Token (see https://docs.chronosphere.io/administer/accounts-teams/personal-access-tokens)")

    args = parser.parse_args()
    args.text = get_search_text(args)
    args.kind_filter = get_kind_filter(args)
    args.domain = get_and_validate_domain(args)
    args.token = get_and_validate_token(args)
    return args


def get_search_text(args):
    text = " ".join(args.text).strip()
    args.text_lower = text.lower()
    sys.stderr.write(f"Query Text: {text}\n")
    return text


def get_kind_filter(args):
    kind_filter = []
    if args.text.lower().startswith("d:"):
        kind_filter = ["dashboards"]
    elif args.text.lower().startswith("t:"):
        kind_filter = ["teams"]
    elif args.text.lower().startswith("c:"):
        kind_filter = ["collections"]
    elif args.text.lower().startswith("m:"):
        kind_filter = ["monitors"]
    elif args.text.lower().startswith("s:"):
        kind_filter = ["services"]
    if kind_filter:
        # update args.text to remove the prefix
        args.text = args.text[2:].strip()
        args.text_lower = args.text.lower()
    else:
        # default to all kinds
        kind_filter = ["dashboards", "teams", "collections", "monitors", "services"]
    sys.stderr.write(f"Kind Filter: {kind_filter}\n")
    return kind_filter


def get_and_validate_domain(args):
    domain = os.getenv("CHRONOSPHERE_DOMAIN", args.domain)
    if domain is None or len(domain) <= 0:
        raise Exception("CHRONOSPHERE_DOMAIN not specified.")
    if not domain.startswith("http"):
        domain = "https://" + domain
    if domain.endswith("/"):
        domain = domain.rstrip("/")
    sys.stderr.write(f"CHRONOSPHERE_DOMAIN: {domain}\n")
    return domain


def get_and_validate_token(args):
    token = os.getenv("CHRONOSPHERE_API_TOKEN", args.token)
    if token is None or len(token) <= 0:
        raise Exception("CHRONOSPHERE_API_TOKEN not specified.")
    sys.stderr.write(f"CHRONOSPHERE_API_TOKEN: {token}\n")
    return token


def search_chronosphere(args):
    query_data = create_search_query(args)
    req = urllib.request.Request(
        f"{args.domain}/api/v1/gql/query",
        headers={"API-Token": args.token, "Content-Type": "application/json; charset=utf-8"},
        data=json.dumps(query_data).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        try:
            response = json.loads(r.read())
        except ValueError:
            raise Exception("Failed to parse JSON response")
    if "message" in response:
        raise Exception(response["message"])
    return response.get("data", {}).get("searchV2", {}).get("items") or []


def create_search_query(args):
    gql_query = """
    query Search($input: SearchQuery!) {
        searchV2(input: $input) {
            items {
                type
                name
                slug
                isFavorite
                isMigratedDashboard
                team {
                    name
                    slug
                    __typename
                }
                collection {
                    name
                    type
                    slug
                    __typename
                }
                __typename
            }
            totalCount
            __typename
        }
    }
    """
    data = {
        "query": gql_query,
        "variables": {
            "input": {"kindFilter": args.kind_filter, "query": args.text},
        },
    }
    return data


def default_alfred_items(args):
    items = []
    if "dashboards" in args.kind_filter:
        items.append({
            "type": "default",
            "title": "Dashboards (d:)",
            "subtitle": f'Search dashboards for "{args.text}"',
            "arg": f"{args.domain}/dashboards/?searchText=" + urllib.parse.quote_plus(args.text),
            "match": "d: search dashboards",
            "icon": {
                "path": "./assets/search.png",
            },
        })
    if "teams" in args.kind_filter:
        items.append({
            "type": "default",
            "title": "Teams (t:)",
            "subtitle": f'Search teams for "{args.text}"',
            "arg": f"{args.domain}/teams/?searchText=" + urllib.parse.quote_plus(args.text),
            "match": "t: search teams",
            "icon": {
                "path": "./assets/search.png",
            },
        })
    if "collections" in args.kind_filter:
        items.append({
            "type": "default",
            "title": "Collections (c:)",
            "subtitle": f'Search collections for "{args.text}"',
            "arg": f"{args.domain}/collections/?searchText=" + urllib.parse.quote_plus(args.text),
            "match": "c: search collections",
            "icon": {
                "path": "./assets/search.png",
            },
        })
    if "monitors" in args.kind_filter:
        items.append({
            "type": "default",
            "title": "Monitors (m:)",
            "subtitle": f'Search monitors for "{args.text}"',
            "arg": f"{args.domain}/monitors/?searchText=" + urllib.parse.quote_plus(args.text),
            "match": "m: search monitors",
            "icon": {
                "path": "./assets/search.png",
            },
        })
    if "services" in args.kind_filter:
        items.append({
            "type": "default",
            "title": "Services (s:)",
            "subtitle": f'Search services for "{args.text}"',
            "arg": f"{args.domain}/services/?searchText=" + urllib.parse.quote_plus(args.text),
            "match": "m: search services",
            "icon": {
                "path": "./assets/search.png",
            },
        })
    prefix_items = []
    suffix_items = []
    for item in items:
        if not args.text_lower or args.text_lower in item["match"]:
            prefix_items.append(item)
        else:
            suffix_items.append(item)
    return prefix_items, suffix_items


def convert_to_alfred_items(search_results, args):
    items = []
    prefix_defaults, suffix_defaults = default_alfred_items(args)
    items.extend(prefix_defaults)
    for item in search_results:
        # docs: https://www.alfredapp.com/help/workflows/inputs/script-filter/json/
        if item["type"] == "dashboards":
            subtitle = item["team"]["name"]
            if item.get("collection"):
                subtitle = f"{subtitle} - {item['collection']['name']}"
            items.append({
                "uid": item["slug"],
                "type": "default",
                "title": f'Dashboard: {item["name"]}',
                "subtitle": subtitle,
                "arg": f"{args.domain}/dashboards/{item['slug']}",
                "icon": {
                    "path": "./assets/dashboards.png",
                },
            })
        elif item["type"] == "teams":
            items.append({
                "uid": item["slug"],
                "type": "default",
                "title": f'Team: {item["name"]}',
                "subtitle": "Team",
                "arg": f"{args.domain}/teams/{item['slug']}",
                "icon": {
                    "path": "./assets/teams.png",
                },
            })
        elif item["type"] == "collections":
            items.append({
                "uid": item["slug"],
                "type": "default",
                "title": f'Collection: {item["name"]}',
                "subtitle": item["team"]["name"],
                "arg": f"{args.domain}/collections/{item['slug']}",
                "icon": {
                    "path": "./assets/collections.png",
                },
            })
        elif item["type"] == "monitors":
            subtitle = item["team"]["name"]
            if item.get("collection"):
                subtitle = f"{subtitle} - {item['collection']['name']}"
            items.append({
                "uid": item["slug"],
                "type": "default",
                "title": f'Monitor: {item["name"]}',
                "subtitle": subtitle,
                "arg": f"{args.domain}/monitors/{item['slug']}",
                "icon": {
                    "path": "./assets/monitors.png",
                },
            })
    items.extend(suffix_defaults)
    return items


try:
    args = parse_args()
    results = search_chronosphere(args)
    alfred_items = convert_to_alfred_items(results, args)
    sys.stdout.write(json.dumps({
        "items": alfred_items
    }))

except Exception as e:
    sys.stdout.write(json.dumps({
        "items": [{
            "title": "Error in Chronosphere search",
            "subtitle": "Details: " + str(e),
            "valid": False,
        }]
    }))
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
