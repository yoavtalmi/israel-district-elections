import googlemaps
import json
import os

import numpy as np
import pandas as pd
import time
import selenium
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from elecetions_constatns import ElectionsConstants

chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--enable-logging')
chrome_options.add_argument('--v=1')

# Set up ChromeDriver service
chrome_service = Service('/usr/local/bin/chromedriver')

# Initialize the WebDriver with the specified options and service
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
driver.get('https://votes25.bechirot.gov.il/ballotresults')


def load_ballots() -> pd.DataFrame:
    return pd.read_csv(ElectionsConstants.RAW_BALLOTS_PATH)


def preprocess_ballots(ballots: pd.DataFrame) -> pd.DataFrame:
    ballots[ElectionsConstants.TOWN_NAME] = ballots[ElectionsConstants.TOWN_NAME].str.replace('  ', ' ')
    return ballots


def extract_options(element_id: str) -> list[str]:
    """
    Extract the options from a dropdown list element.
    :param element_id: the ID of the dropdown list element
    :return: a list of options extracted from the dropdown list
    """
    # Click the input to show the dropdown list
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, element_id)))
    input_element = driver.find_element(By.ID, element_id)
    input_element.click()
    time.sleep(2)  # Allow time for the dropdown to populate

    # Extract all list items
    options = driver.find_elements(By.XPATH, f"//ul[contains(@id, 'awesomplete_list_') and @aria-label='undefined']/li")
    return [option.text for option in options if option.get_attribute('role') == 'option']


def safely_interact_with_element(callback, *args, max_attempts=3):
    """
    Safely interact with an element by handling StaleElementReferenceException.
    :param callback: selenium function to interact with the element
    :param args: arguments to pass to the callback function
    :param max_attempts: maximum number of attempts to interact with the element
    :return: callback result
    """
    attempts = 0
    while attempts < max_attempts:
        try:
            return callback(*args)
        except selenium.common.exceptions.StaleElementReferenceException:
            print(f"Encountered StaleElementReferenceException, retrying... Attempt {attempts+1}/{max_attempts}")
            time.sleep(1)  # Wait a bit before retrying
        attempts += 1
    raise Exception("Failed to interact with the element after several attempts.")


def select_town(town):
    town_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, ElectionsConstants.TOWN_HTML_ELEMENT)))
    town_input.clear()
    town_input.send_keys(town)
    time.sleep(1)  # Allow time for the autocomplete to populate

    # Wait for the autocomplete suggestions to be visible
    suggestions_xpath = "//ul[contains(@id, 'awesomplete_list_') and @aria-label='undefined']/li"
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, suggestions_xpath)))

    # Get all suggestions that match the text exactly
    suggestions = driver.find_elements(By.XPATH, suggestions_xpath)
    for suggestion in suggestions:
        if suggestion.text == town:
            suggestion.click()  # Click the exact match
            break
    else:
        raise Exception(f"No exact match found for {town}")


def extract_towns_ballots():
    """
    Extract the towns and the ballots for each town from the website.
    List of towns is extracted from the 'Town' dropdown list.
    List of ballots is extracted from the 'PollingStation' dropdown list.
    The extracted data is saved in the ElectionsConstants.BALLOTS_LOCATION_NAMES_PATH directory.
    :return:
    """
    os.mkdir(ElectionsConstants.BALLOTS_LOCATION_NAMES_PATH) if \
        not os.path.exists(ElectionsConstants.BALLOTS_LOCATION_NAMES_PATH) else None
    ballots_location_names = os.listdir(ElectionsConstants.BALLOTS_LOCATION_NAMES_PATH)

    # Extract towns
    towns = extract_options(ElectionsConstants.TOWN_HTML_ELEMENT)

    # For each town, extract ballots
    for town in towns:
        if town == '- בחר ישוב -' or f'{town}.json' in ballots_location_names:
            print(f'{town} already extracted, skipping...')
            continue
        print(f'Extracting ballots for {town}')
        town_ballots = {ElectionsConstants.TOWN: town}
        try:
            def attempt_select_town():
                select_town(town)  # Updated to use the new function

            flag = False
            while not flag:
                # Use the safely_interact_with_element function to handle stale elements
                safely_interact_with_element(attempt_select_town)
                time.sleep(1)  # Allow time for the page to update

            # Extract ballots for the selected town
                ballots = extract_options(ElectionsConstants.POLLING_STATION_HTML_ELEMENT)
                if not ballots:
                    print(f'No ballots found for {town}, retrying...')
                    continue
                else:
                    flag = True

            print(f'Extracted {len(ballots)} ballots')
            town_ballots[ElectionsConstants.BALLOTS] = ballots
            with open(f'{ElectionsConstants.BALLOTS_LOCATION_NAMES_PATH}/{town}.json', 'w', encoding='utf-8') as f:
                json.dump(town_ballots, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'Failed to extract ballots for {town}: {e}'
                  f'\nSkipping to the next town...')
            continue

        # Optional: Clear the selection or refresh the page to reset the state
        driver.refresh()

    driver.quit()


def load_ballots_location_names() -> pd.DataFrame:
    """
    Load the extracted towns and ballots from the ElectionsConstants.BALLOTS_LOCATION_NAMES_PATH directory.
    :return: a DataFrame containing the extracted towns and ballots
    """
    ballots_location_names = os.listdir(ElectionsConstants.BALLOTS_LOCATION_NAMES_PATH)
    towns_ballots = []
    for file in ballots_location_names:
        with open(f'{ElectionsConstants.BALLOTS_LOCATION_NAMES_PATH}/{file}', 'r', encoding='utf-8') as f:
            town_ballots = json.load(f)
        for ballot in town_ballots[ElectionsConstants.BALLOTS]:
            if '- בחר קלפי -' == ballot:
                continue
            towns_ballots.append({ElectionsConstants.TOWN_NAME: town_ballots[ElectionsConstants.TOWN],
                                  ElectionsConstants.LOCATION: ballot.split(' קלפי ')[0],
                                  ElectionsConstants.BALLOT_ID: int(ballot.split(' ')[-1])})
    ballots_location_df = pd.DataFrame(towns_ballots)
    return ballots_location_df


def merge_meta_ballots():
    """
    Merge the ballots and the ballots meta DataFrames.
    The merged DataFrame is saved in the ElectionsConstants.MERGED_BALLOTS_PATH file.
    :return:
    """
    ballots = load_ballots()
    ballots = preprocess_ballots(ballots)
    ballots_location_df = load_ballots_location_names()
    ballots_merged = pd.merge(ballots, ballots_location_df, on=[ElectionsConstants.TOWN_NAME,
                                                                ElectionsConstants.BALLOT_ID])
    ballots_merged = ballots_merged.groupby([ElectionsConstants.TOWN_NAME, ElectionsConstants.BALLOTS_CLUSTER]).agg(
        {col: 'sum' for col in ballots_merged.columns if col not in [ElectionsConstants.TOWN_NAME,
                                                                     ElectionsConstants.BALLOTS_CLUSTER,
                                                                     ElectionsConstants.LOCATION]} |
        {ElectionsConstants.LOCATION: 'first'}
    ).reset_index()
    ballots_merged = ballots_merged[ballots_merged[ElectionsConstants.TOWN_NAME] != ElectionsConstants.LATE_VOTES]
    ballots_merged.to_csv(ElectionsConstants.MERGED_BALLOTS_PATH, index=False)


def download_coordination_with_googlemap(ballots: pd.DataFrame):
    """
    Download the coordinates of the towns using Google Maps API.
    The coordinates are saved in the ElectionsConstants.BALLOTS_WITH_COORDINATES_PATH file.
    :param ballots: a DataFrame containing the towns
    :return:
    """
    # Load the Google Maps API key from the environment variable
    api_key = os.getenv('GCP_KEY')
    if api_key is None:
        raise Exception("Google Maps API key not found. Set the GCP_KEY environment variable.")
    gmaps = googlemaps.Client(key=api_key)
    lat = []
    lng = []
    localties = []
    town_localities = []
    current_town = ''
    for idx, row in ballots.iterrows():
        try:
            if row[ElectionsConstants.TOWN_NAME] != current_town:
                current_town = row[ElectionsConstants.TOWN_NAME]
                geocode_result = gmaps.geocode(current_town)
                town_locality = [x['long_name'] for x in geocode_result[0]['address_components']
                                 if ElectionsConstants.LOCALITY in x['types']]
                town_locality = town_locality[0] if len(town_locality) > 0 else None
            town_localities.append(town_locality)
        except Exception as e:
            print(f'Failed to extract coordinates for the town {current_town}: {e}'
                  f'\nSkipping to the next ballots...')
            town_localities.append(None)
        try:
            addres = row[ElectionsConstants.TOWN_NAME] + ', ' + row[ElectionsConstants.LOCATION]
            geocode_result = gmaps.geocode(addres)
            lat.append(geocode_result[0]['geometry'][ElectionsConstants.LOCATION][ElectionsConstants.LAT])
            lng.append(geocode_result[0]['geometry'][ElectionsConstants.LOCATION][ElectionsConstants.LNG])
            locality = [x['long_name'] for x in geocode_result[0]['address_components']
                        if ElectionsConstants.LOCALITY in x['types']]
            locality = locality[0] if len(locality) > 0 else None
            localties.append(locality)
        except Exception as e:
            print(f'Failed to extract coordinates for {addres}: {e}'
                  f'\nSkipping to the next ballots...')
            lat.append(None)
            lng.append(None)
            localties.append(None)
            continue
    ballots[ElectionsConstants.LAT] = lat
    ballots[ElectionsConstants.LNG] = lng
    ballots[ElectionsConstants.LOCALITY] = localties
    ballots[ElectionsConstants.TOWN_LOCALITY] = town_localities
    ballots.to_csv(ElectionsConstants.BALLOTS_WITH_COORDINATES_PATH, index=False)


def fill_small_town_location():
    """
    Fill the missing locations of the small towns.
    We use the Google Maps API to extract the coordinates of the towns and not the location.
    The filled DataFrame is saved in the 'data/ballots_with_coordinates_filled.csv' file.
    :return:
    """
    api_key = os.getenv('GCP_KEY')
    if api_key is None:
        raise Exception("Google Maps API key not found. Set the GCP_KEY environment variable.")
    gmaps = googlemaps.Client(key=api_key)
    ballots = pd.read_csv(ElectionsConstants.BALLOTS_WITH_COORDINATES_PATH)
    replace_dict = {'אשדוד': 'Ashdod', 'אשקלון': 'Ashkelon', 'בית שמש': 'Bet Shemesh', 'בני ברק': 'Bnei Brak',
                    'גבעתיים': "Giv'atayim", 'הרצליה': 'Herzliya', 'חדרה': 'Hadera',
                    'חולון': 'Holon', 'טבריה': 'Tiberias', 'טייבה': 'Tayibe', 'ירושלים': 'Jerusalem',
                    'כפר סבא': 'Kefar Sava', 'לוד': 'Lod', 'נצרת': 'Nazareth', 'נתניה': 'Netanya',
                    'עפולה': 'Afula', 'פתח תקווה': 'Petah Tikva', 'קריית אתא': 'Kiryat Ata',
                    'ראשון לציון': 'Rishon LeTsiyon', 'רחובות': 'Rehovot',
                    'רמלה': 'Ramla',
                    'תל אביב - יפו': 'Tel Aviv-Yafo', 'תל אביב-יפו': 'Tel Aviv-Yafo', 'Tel Aviv-Jaffa': 'Tel Aviv-Yafo',
                    'Pardes Hana-Karkur': 'Pardes Hanna-Karkur', 'Nazareth Illit': 'Nof HaGalil',
                    "Modi'in-Maccabim-Re'ut": "Modi'in Makabim-Re'ut", "Ma'alot Tarshiha": "Ma'alot-Tarshiha",
                    "Kohav Ya'ir": "Kochav Yair Tzur Yigal", "Kisra Sume'a": "Kisra-Sumei",
                    "Kiryat Motskin": "Kiryat Motzkin", "Hertsliya": "Herzliya", "Beit Shemesh": "Bet Shemesh",
                    "Beersheba": "Be'er Sheva", 'Akko': 'Acre', "Zihron Ya'akov": "Zikhron Ya'akov",
                    'Tverya': 'Tiberias', 'Kfar Sava': 'Kefar Sava', 'Nahariya': 'Nahariyya',
                    'Natsrat Ilit': 'Nof HaGalil',}
    ballots[ElectionsConstants.LOCALITY] = ballots[ElectionsConstants.LOCALITY].replace(replace_dict)
    ballots.loc[
        (ballots[ElectionsConstants.LOCALITY] != ballots[ElectionsConstants.TOWN_LOCALITY])
        & (ballots[ElectionsConstants.TOWN_LOCALITY].notnull()),
        [ElectionsConstants.LAT, ElectionsConstants.LNG, ElectionsConstants.LOCALITY]] = None
    for idx, row in ballots.iterrows():
        if np.isnan(row[ElectionsConstants.LAT]):
            try:
                address = row[ElectionsConstants.TOWN_NAME]
                neighborhood_dict = {'תל אביב יפו': 'תל אביב', 'כרם יבנה ישיבה': 'כרם ביבנה',
                                     'מודיעיןמכביםרעות': 'מכבים רעות'}
                if address in neighborhood_dict:
                    address = neighborhood_dict[address]
                geocode_result = gmaps.geocode(address)
                if 'locality' not in geocode_result[0]['types']:
                    print(f'Failed to extract coordinates for {address}:'
                          f'\nSkipping to the next ballots...')
                    continue
                ballots.loc[idx, ElectionsConstants.LAT] = \
                    geocode_result[0]['geometry'][ElectionsConstants.LOCATION][ElectionsConstants.LAT]
                ballots.loc[idx, ElectionsConstants.LNG] = \
                    geocode_result[0]['geometry'][ElectionsConstants.LOCATION][ElectionsConstants.LNG]
                ballots.loc[idx, ElectionsConstants.LOCALITY] = \
                    [x['long_name'] for x in geocode_result[0]['address_components']
                     if ElectionsConstants.LOCALITY in x['types']][0]
            except Exception as e:
                print(f'Failed to extract coordinates for {address}: {e}'
                      f'\nSkipping to the next ballots...')
                continue
    ballots.to_csv('data/ballots_with_coordinates_filled.csv', index=False)


if __name__ == '__main__':
    # extract_towns_ballots()
    # merge_meta_ballots()
    # ballots_merged = pd.read_csv(ElectionsConstants.MERGED_BALLOTS_PATH)
    # download_coordination_with_googlemap(ballots=ballots_merged)
    fill_small_town_location()
