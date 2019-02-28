import json
import re
import os
from bs4 import BeautifulSoup
from getpass import getpass
from Levenshtein import distance
import requests
import hashlib


def fetch_database(country):
    """Fetches xeno-canto database for a specific country and start and end page. Country should be a string,
    for example, 'Papua New Guinea', and start_page and end_page should be integers."""

    filename = country + '.json'

    # Initialize containers to store urls, scientific names, and common names
    urls = []
    scientific_names = []
    common_names = []

    # Get the available page range for the database
    ROOT = 'https://www.xeno-canto.org/explore?query=+cnt%3A"' + country.title().replace(' ', '+') + '"&view=2'
    r = requests.get(ROOT)
    soup = BeautifulSoup(r.content, features="html5lib")
    try:
        page_in_here = str(soup.find('nav', 'results-pages')).split('\n')[-6].strip()
        end_page = int(re.search('pg=(\w+)', page_in_here).group(1))
    except IndexError:
        end_page = 1

    # Get urls, scientific names, and common names from html
    for i in range(1, end_page + 1):
        URL = ROOT + '&pg=' + str(i)
        r = requests.get(URL)
        temp_names = []
        temp_urls = []

        if r.status_code != 200:
            print("Page {} didn't load or doesn't exist...".format(i))
        else:
            print('Processing page {}/{}...'.format(i, end_page), end='\r')
            soup = BeautifulSoup(r.content, features="html5lib")
            big_list = str(soup.find_all("td"))
            for line in big_list.split("\n"):
                if ".mp3" in line or ".MP3" in line:
                    prefix = 'https://'
                    url = prefix + line.strip().split('"')[3][2:]
                    temp_urls.append(url)
                elif "common-name" in line or "ID under discussion" in line:
                    temp_names.append(line.strip())

        if len(temp_names) == len(temp_urls):
            for name in temp_names:
                if "span class" in name:
                    scientific_name = name.split('">')[1][18:].replace('-', ' ').lower()
                    common_name = name.split('">')[2].split('<')[0].lower()
                    scientific_names.append(scientific_name)
                    common_names.append(common_name)
                else:
                    scientific_names.append('unknown')
                    common_names.append('unknown')
            urls += temp_urls
        else:
            print('Issue on page {}: number of mp3s did not match number of listings.'.format(i))

    # Build database
    print("Building database...")
    database = {name:{'urls': [], 'scientific_name': set()} for name in set(common_names)}

    for i in range(len(urls)):
        database[common_names[i]]['urls'].append(urls[i])
        database[common_names[i]]['scientific_name'].add(scientific_names[i])

    for k, v in database.items():
        database[k]['scientific_name'] = list(database[k]['scientific_name'])[0]

    if "" in database.keys():
        del database[""]

    # Save database
    if not os.path.exists('databases'):
        os.makedirs('databases')

    save_path = 'databases/' + filename
    with open(save_path, 'w') as fp:
        json.dump(database, fp, indent=2, sort_keys=True)

    print('Done.')


def download_mp3s(country, bird, search_by='c'):
    """Downloads mp3 for a desired bird in a specific country."""

    db_path = 'databases/' + country.lower() + '.json'
    bird = bird.lower()

    if not os.path.isfile(db_path):
        print('Database not found. Please download it first.')
        return

    # Load in database
    with open(db_path, 'r') as fp:
        database = json.load(fp)

    # Generate inverse map
    inverse_db = {database[key]['scientific_name']: {'common_name': key,
                                                     'urls': database[key]['urls']} for key in database.keys()}

    if search_by == 'c':
        # Select birds to download
        to_download = []
        for key in database.keys():
            if bird in key:
                to_download.append(key)

    elif search_by == 's':
        # Select birds to download
        to_download = []
        for key in inverse_db.keys():
            if bird in key:
                to_download.append(inverse_db[key]['common_name'])

    if len(to_download) > 0:
        print('\nAbout to download mp3s for:')
        for key in to_download:
            print("{} ({}): {} files".format(key.title(),
                                                 database[key]['scientific_name'].capitalize(),
                                                 len(database[key]['urls'])))
        query = getpass(prompt='\nDownload all files now? (y/n) ')
        if query == 'y':
            for item in to_download:
                count = 0
                urls = database[item]['urls']
                for i, url in enumerate(urls):

                    # Make folder if it doesn't already exist.
                    root = country + '/' + item
                    if not os.path.exists(root):
                        os.makedirs(root)

                    # Generate hash code for the file to be downloaded.
                    hashcode = hashlib.md5(url.encode('utf-8')).hexdigest()[-5:]

                    # Check if the file is already in the folder.
                    exists = False
                    for file in os.listdir(country + '/' + item):
                        if hashcode in file:
                            exists = True

                    # Download file if it isn't already present.
                    if not exists:
                        count += 1
                        data = requests.get(url)
                        prefix = str(i + 1).zfill(3)
                        scientific_name = database[item]['scientific_name']
                        filename = prefix + '-' + hashcode + '-' + scientific_name + '.mp3'
                        full_path = root + '/' + filename
                        with open(full_path, 'wb') as f:
                            print('Downloading {}'.format(filename), end='\r')
                            f.write(data.content)
                if count == 0:
                    print('No new files downloaded for {}'.format(item.capitalize()))
                else:
                    print()
        else:
            return
    else:
        print('No birds found with that name.')


def suggest(countries, search_term):
    """Suggests a country in the database for a misspelled search term."""

    levenshtein_distances = [distance(country, search_term) for country in countries]

    min_distance = float('inf')
    best_idx = 0
    for i, dist in enumerate(levenshtein_distances):
        if dist <= min_distance:
            min_distance = dist
            best_idx = i

    return countries[best_idx]

def main():

    if not os.path.exists('databases'):
        os.makedirs('databases')

    flag = True

    while flag:
        print()
        print("Enter one of the following selections:")
        print("1. Download database")
        print("2. Download mp3s.")
        print("3. Type q to quit at any time.")

        query = input('Selection: ')

        if query == '1':
            print("\nWhat country do you want to download the database for?")
            country = str(input()).lower()
            if os.path.isfile('databases/' + country + '.json'):
                query = getpass(prompt='Database for this country already exists, overwrite? (y/n)\n')
                if query == 'n':
                    continue
                else:
                    pass
            with open('countries.txt', 'r') as f:
                countries = f.readlines()
                countries = [listing.strip().lower() for listing in countries]
                if country not in countries:
                    suggestion = suggest(countries, country)
                    print('"{}" is not an available country for download. Did you mean "{}"?'.format(country, suggestion))
                    query = input('Type y to download database for {} or anything else to return to the main screen: '.format(suggestion))
                    if query == 'y':
                        fetch_database(suggestion)
                    else:
                        continue
            fetch_database(country)
            continue

        elif query == '2':
            print('\nQuery database using common or species name? Type c or s.')
            search_by = str(input('Selection: ')).lower()
            while search_by != 'c' and search_by != 's':
                print('Please re-enter that. Type c or s.')
                search_by = str(input('Selection: ')).lower()
            print('\nWhat country and bird do you want to download mp3s for?')
            country = str(input('Country: ')).lower()
            bird = str(input('Bird: ')).lower()
            download_mp3s(country, bird, search_by)
            continue

        elif query == 'q':
            flag = False

        else:
            print('Sorry, try entering that again...')
            continue

if __name__ == '__main__':
    main()
