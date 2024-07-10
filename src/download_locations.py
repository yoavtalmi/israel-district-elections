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
    return pd.read_csv('data/ballots.csv')


def preprocess_ballots(ballots: pd.DataFrame) -> pd.DataFrame:
    ballots['שם ישוב'] = ballots['שם ישוב'].str.replace('  ', ' ')
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
        EC.element_to_be_clickable((By.ID, 'Town')))
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
    The extracted data is saved in the 'data/ballots_location_names' directory.
    :return:
    """
    os.mkdir('data/ballots_location_names') if not os.path.exists('data/ballots_location_names') else None
    ballots_location_names = os.listdir('data/ballots_location_names')

    # Extract towns
    towns = extract_options('Town')


    # For each town, extract ballots
    for town in towns:
        if town == '- בחר ישוב -' or f'{town}.json' in ballots_location_names:
            print(f'{town} already extracted, skipping...')
            continue
        print(f'Extracting ballots for {town}')
        town_ballots = {'town': town}
        try:
            def attempt_select_town():
                select_town(town)  # Updated to use the new function

            flag = False
            while not flag:
                # Use the safely_interact_with_element function to handle stale elements
                safely_interact_with_element(attempt_select_town)
                time.sleep(1)  # Allow time for the page to update

            # Extract ballots for the selected town
                ballots = extract_options('PollingStation')
                if not ballots:
                    print(f'No ballots found for {town}, retrying...')
                    continue
                else:
                    flag = True

            print(f'Extracted {len(ballots)} ballots')
            town_ballots['ballots'] = ballots
            with open(f'data/ballots_location_names/{town}.json', 'w', encoding='utf-8') as f:
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
    Load the extracted towns and ballots from the 'data/ballots_location_names' directory.
    :return: a DataFrame containing the extracted towns and ballots
    """
    ballots_location_names = os.listdir('data/ballots_location_names')
    towns_ballots = []
    for file in ballots_location_names:
        with open(f'data/ballots_location_names/{file}', 'r', encoding='utf-8') as f:
            town_ballots = json.load(f)
        for ballot in town_ballots['ballots']:
            if '- בחר קלפי -' == ballot:
                continue
            towns_ballots.append({'שם ישוב': town_ballots['town'], 'location': ballot.split(' קלפי ')[0],
                                  'ברזל': int(ballot.split(' ')[-1])})
    ballots_location_df = pd.DataFrame(towns_ballots)
    return ballots_location_df


def merge_meta_ballots():
    """
    Merge the ballots and the ballots meta DataFrames.
    The merged DataFrame is saved in the 'data/ballots_merged.csv' file.
    :return:
    """
    ballots = load_ballots()
    ballots = preprocess_ballots(ballots)
    ballots_location_df = load_ballots_location_names()
    ballots_merged = pd.merge(ballots, ballots_location_df, on=['שם ישוב', 'ברזל'])
    ballots_merged = ballots_merged.groupby(['שם ישוב', 'ריכוז']).agg(
        {col: 'sum' for col in ballots_merged.columns if col not in ['שם ישוב', 'ריכוז', 'location']} |
        {'location': 'first'}
    ).reset_index()
    ballots_merged = ballots_merged[ballots_merged['שם ישוב'] != 'מעטפות חיצוניות']
    ballots_merged.to_csv('data/ballots_merged.csv', index=False)


def download_coordination_with_googlemap(ballots: pd.DataFrame):
    """
    Download the coordinates of the towns using Google Maps API.
    The coordinates are saved in the 'data/ballots_with_coordinates.csv' file.
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
    for idx, row in ballots.iterrows():
        try:
            addres = row['שם ישוב'] + ' ' + row['location']
            geocode_result = gmaps.geocode(addres)
            lat.append(geocode_result[0]['geometry']['location']['lat'])
            lng.append(geocode_result[0]['geometry']['location']['lng'])
        except Exception as e:
            print(f'Failed to extract coordinates for {addres}: {e}'
                  f'\nSkipping to the next ballots...')
            lat.append(None)
            lng.append(None)
            continue
    ballots['lat'] = lat
    ballots['lng'] = lng
    ballots.to_csv('data/ballots_with_coordinates.csv', index=False)


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
    ballots = pd.read_csv('data/ballots_with_coordinates.csv')
    for idx, row in ballots.iterrows():
        if np.isnan(row['lat']):
            try:
                addres = row['שם ישוב']
                geocode_result = gmaps.geocode(addres)
                if 'locality' not in geocode_result[0]['types']:
                    print(f'Failed to extract coordinates for {addres}: {e}'
                          f'\nSkipping to the next ballots...')
                    continue
                ballots.loc[idx, 'lat'] = geocode_result[0]['geometry']['location']['lat']
                ballots.loc[idx, 'lng'] = geocode_result[0]['geometry']['location']['lng']
            except Exception as e:
                print(f'Failed to extract coordinates for {addres}: {e}'
                      f'\nSkipping to the next ballots...')
                continue
    ballots.to_csv('data/ballots_with_coordinates_filled.csv', index=False)


if __name__ == '__main__':
    fill_small_town_location()
