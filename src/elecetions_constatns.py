from dataclasses import dataclass


@dataclass
class ElectionsConstants:
    BALLOT_ID: str = 'ברזל'
    BALLOTS: str = 'ballots'
    BALLOTS_CLUSTER: str = 'ריכוז'
    BALLOTS_LOCATION_NAMES_PATH: str = "data/ballots_location_names"
    BALLOTS_WITH_COORDINATES_PATH: str = "data/ballots_with_coordinates.csv"
    BALLOTS_WITH_COORDINATES_FILLED_PATH: str = "data/ballots_with_coordinates_filled.csv"
    DISTRICT: str = 'district'
    DISTRICT_VOTE_VARIANCE: float = 0.05
    LAT: str = 'lat'
    LATE_VOTES: str = 'מעטפות חיצוניות'
    LOCALITY: str = 'locality'
    LOCATION: str = 'location'
    LNG: str = 'lng'
    MERGED_BALLOTS_PATH: str = "data/ballots_merged.csv"
    NUMBER_OF_SEATS: int = 120
    RAW_BALLOTS_PATH: str = "data/ballots.csv"
    REGISTRED_VOTERS: str = 'בזב'
    POLLING_STATION_HTML_ELEMENT: str = 'PollingStation'
    TOWN: str = 'town'
    TOWN_HTML_ELEMENT: str = 'TOWN'
    TOWN_LOCALITY: str = 'town_locality'
    TOWN_NAME: str = "שם ישוב"