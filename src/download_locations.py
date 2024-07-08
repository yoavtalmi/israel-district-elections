import json
import os
import pandas as pd
import time
import selenium
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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


def pre_process_ballots(ballots: pd.DataFrame) -> pd.DataFrame:
    """
    Pre-process the ballots DataFrame by grouping and summing the data by the town and the polling station.
    :param ballots: ballots DataFrame
    :return:
    """
    ballots = ballots.groupby(['שם ישוב', 'ריכוז']).agg(
        {col: 'sum' for col in ballots.columns if col not in ['שם ישוב', 'ריכוז', 'ברזל']} |
        {'ברזל': 'first'}
    ).reset_index()
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
        if town == '- בחר ישוב -':
            continue
        if f'{town}.json' in ballots_location_names:
            print(f'{town} already extracted, skipping...')
            continue
        print(f'Extracting ballots for {town}')
        town_ballots = {'town': town}
        try:
            def select_town():
                town_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'Town')))
                town_input.clear()
                town_input.send_keys(town)
                time.sleep(1)  # Allow time for the autocomplete to populate
                town_input.send_keys(Keys.RETURN)  # To select the town

            # Use the safely_interact_with_element function to handle stale elements
            flag = False
            while not flag:
                safely_interact_with_element(select_town)
                time.sleep(1)
                # Extract ballots for the selected town
                ballots = extract_options('PollingStation')
                if len(ballots) > 1:
                    flag = True
                else:
                    print(f'No ballots found for {town}, retrying...')
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


if __name__ == '__main__':
    extract_towns_ballots()
