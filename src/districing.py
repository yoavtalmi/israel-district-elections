import pandas as pd

from sklearn.cluster import KMeans

from elecetions_constatns import ElectionsConstants


def load_data() -> pd.DataFrame:
    return pd.read_csv(ElectionsConstants.BALLOTS_WITH_COORDINATES_FILLED_PATH)


def pre_process_data(ballots: pd.DataFrame) -> pd.DataFrame:
    ballots = ballots.dropna(subset=[ElectionsConstants.LAT, ElectionsConstants.LNG])
    return ballots


def get_cities(ballots: pd.DataFrame) -> pd.DataFrame:
    return ballots.groupby([ElectionsConstants.TOWN_NAME]).sum().reset_index()\
        .sort_values(by=ElectionsConstants.REGISTRED_VOTERS, ascending=False)


def get_cities_districts(ballots: pd.DataFrame) -> pd.DataFrame:
    cities = get_cities(ballots)
    cities_names = cities[ElectionsConstants.TOWN_NAME].values
    overall_voters = cities[ElectionsConstants.REGISTRED_VOTERS].sum()
    single_seat = overall_voters/ElectionsConstants.NUMBER_OF_SEATS
    seats_dict = {}
    seat_number = 0
    seats_dict[seat_number] = {ElectionsConstants.REGISTRED_VOTERS: 0, ElectionsConstants.LAT: -1,
                               ElectionsConstants.LNG: -1}
    ballots[ElectionsConstants.DISTRICT] = None
    for city in cities_names:
        directions_counter = 0
        city_ballots = ballots[ballots[ElectionsConstants.TOWN_NAME] == city]
        while sum(city_ballots[ElectionsConstants.DISTRICT].isnull()) > 0:
            if seats_dict[seat_number][ElectionsConstants.REGISTRED_VOTERS] == 0:
                if directions_counter % 4 == 0:
                    city_ballots = city_ballots.sort_values(by=ElectionsConstants.LNG, ascending=False)
                    starting_ballot = city_ballots[city_ballots[ElectionsConstants.DISTRICT].isnull()].iloc[0]
                elif directions_counter % 4 == 1:
                    city_ballots = city_ballots.sort_values(by=ElectionsConstants.LNG, ascending=True)
                    starting_ballot = city_ballots[city_ballots[ElectionsConstants.DISTRICT].isnull()].iloc[0]
                elif directions_counter % 4 == 2:
                    city_ballots = city_ballots.sort_values(by=ElectionsConstants.LAT, ascending=False)
                    starting_ballot = city_ballots[city_ballots[ElectionsConstants.DISTRICT].isnull()].iloc[0]
                else:
                    city_ballots = city_ballots.sort_values(by=ElectionsConstants.LAT, ascending=True)
                    starting_ballot = city_ballots[city_ballots[ElectionsConstants.DISTRICT].isnull()].iloc[0]

                seats_dict[seat_number][ElectionsConstants.REGISTRED_VOTERS] = \
                    starting_ballot[ElectionsConstants.REGISTRED_VOTERS].sum()
                seats_dict[seat_number][ElectionsConstants.LAT] = starting_ballot[ElectionsConstants.LAT]
                seats_dict[seat_number][ElectionsConstants.LNG] = starting_ballot[ElectionsConstants.LNG]
                starting_ballot_id = starting_ballot[ElectionsConstants.BALLOT_ID]
                ballots.loc[ballots[ElectionsConstants.BALLOT_ID] == starting_ballot_id, ElectionsConstants.DISTRICT] = \
                    seat_number
                city_ballots = ballots[ballots[ElectionsConstants.TOWN_NAME] == city] \
                    .sort_values(by=ElectionsConstants.REGISTRED_VOTERS, ascending=False)

            while seats_dict[seat_number][ElectionsConstants.REGISTRED_VOTERS] < single_seat:
                if sum(city_ballots[ElectionsConstants.DISTRICT].isnull()) > 0:
                    city_ballots_with_no_district = city_ballots[city_ballots[ElectionsConstants.DISTRICT].isnull()]
                    city_ballots_with_no_district[f'current_distance'] = \
                        ((city_ballots_with_no_district[ElectionsConstants.LAT] -
                          seats_dict[seat_number][ElectionsConstants.LAT])**2 +
                         (city_ballots_with_no_district[ElectionsConstants.LNG] -
                          seats_dict[seat_number][ElectionsConstants.LNG])**2)
                    city_ballots_with_no_district = city_ballots_with_no_district.sort_values(by='current_distance')
                    closest_ballot = \
                        city_ballots_with_no_district[
                            city_ballots_with_no_district[ElectionsConstants.DISTRICT].isnull()].iloc[0]
                    closest_ballot_id = closest_ballot[ElectionsConstants.BALLOT_ID]
                    ballots.loc[(ballots[ElectionsConstants.BALLOT_ID] == closest_ballot_id)
                                & (ballots[ElectionsConstants.TOWN_NAME] == city), ElectionsConstants.DISTRICT] = \
                        seat_number
                    seats_dict[seat_number][ElectionsConstants.REGISTRED_VOTERS] = \
                        ballots[ballots[ElectionsConstants.DISTRICT] ==
                                seat_number][ElectionsConstants.REGISTRED_VOTERS].sum()
                    seats_dict[seat_number][ElectionsConstants.LAT] = \
                        ballots[ballots[ElectionsConstants.DISTRICT] == seat_number][ElectionsConstants.LAT].mean()
                    seats_dict[seat_number][ElectionsConstants.LNG] = \
                        ballots[ballots[ElectionsConstants.DISTRICT] == seat_number][ElectionsConstants.LNG].mean()
                    city_ballots = ballots[ballots[ElectionsConstants.TOWN_NAME] == city] \
                        .sort_values(by=ElectionsConstants.REGISTRED_VOTERS, ascending=False)
                else:
                    ballots_with_no_district = ballots[ballots[ElectionsConstants.DISTRICT].isnull()]
                    ballots_with_no_district[f'current_distance'] = \
                        ((ballots_with_no_district[ElectionsConstants.LAT] -
                          seats_dict[seat_number][ElectionsConstants.LAT])**2 +
                         (ballots_with_no_district[ElectionsConstants.LNG] -
                          seats_dict[seat_number][ElectionsConstants.LNG])**2)
                    ballots_with_no_district = ballots_with_no_district.sort_values(by='current_distance')
                    closest_ballot = \
                        ballots_with_no_district[
                            ballots_with_no_district[ElectionsConstants.DISTRICT].isnull()].iloc[0]
                    closest_ballot_id = closest_ballot[ElectionsConstants.BALLOT_ID]
                    closest_ballot_town = closest_ballot[ElectionsConstants.TOWN_NAME]
                    ballots.loc[(ballots[ElectionsConstants.BALLOT_ID] == closest_ballot_id) &
                                (ballots[ElectionsConstants.TOWN_NAME] == closest_ballot_town),
                    ElectionsConstants.DISTRICT] \
                        = seat_number
                    seats_dict[seat_number][ElectionsConstants.REGISTRED_VOTERS] = \
                        ballots[ballots[ElectionsConstants.DISTRICT] ==
                                seat_number][ElectionsConstants.REGISTRED_VOTERS].sum()
                    seats_dict[seat_number][ElectionsConstants.LAT] = \
                        ballots[ballots[ElectionsConstants.DISTRICT] == seat_number][ElectionsConstants.LAT].mean()
                    seats_dict[seat_number][ElectionsConstants.LNG] = \
                        ballots[ballots[ElectionsConstants.DISTRICT] == seat_number][ElectionsConstants.LNG].mean()
            seat_number += 1
            directions_counter += 1
            seats_dict[seat_number] = {ElectionsConstants.REGISTRED_VOTERS: 0, ElectionsConstants.LAT: -1,
                                       ElectionsConstants.LNG: -1}

    return ballots


if __name__ == "__main__":
    ballots = load_data()
    ballots = pre_process_data(ballots)
    big_cities_districts = get_cities_districts(ballots)
