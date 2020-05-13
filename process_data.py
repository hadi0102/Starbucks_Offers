import pandas as pd
import numpy as np
import json
from datetime import date
pd.options.mode.chained_assignment = None  # default='warn'


def load_data():
    """
    Load data from json files
    Args:
        - None
    Return:
        - portfolio: info about the offers
        - profile: info about the users
        - transcript: info about the transactions
    """
    portfolio = pd.read_json('data/portfolio.json', orient='records', lines=True)
    profile = pd.read_json('data/profile.json', orient='records', lines=True)
    transcript = pd.read_json('data/transcript.json', orient='records', lines=True)

    portfolio = portfolio.dropna()
    profile = profile.dropna()
    transcript = transcript.dropna()

    return portfolio, profile, transcript


def transform_transcript(df):
    """
    This function does 3 operations:
    1. Clean the value column
    2. Drop duplicates
    2. Add complementary info to transcript data allowing to follow an offer and
    a person
    Args: dataframe, initial transcript DataFrame
    Output: clean dataframe transcript with additional personvalue column
    """
    df['value'] = df['value'].apply(lambda x: list(x.values())[0])
    df = df.drop_duplicates()
    df['personvalue'] = df['person'].astype(str) + '-' + df['value'].astype(str)

    return df


def get_transaction_from_offer(df):
    """
    Get all the offers that were provoked by an offer time_viewed
    Args: df, transcript dataframe with column mixing person and value
    Returns: list of personvalue corresponding to this criteria
    """

    offer_viewed = df[df['event'] == 'offer viewed']['personvalue']

    offer_viewed_and_completed = df[(df['personvalue'].isin(offer_viewed))
                                  & (df['event'] == 'offer completed')]

    offers_leading_to_transaction = []
    for offer in (offer_viewed_and_completed.sort_values('person')['personvalue'].unique()):

        # focus on the transcript for one offer for a user
        offer_timing = df[df['personvalue'] == offer].sort_values('time')

        # selecting the first time the offer was viewed
        time_viewed = offer_timing[offer_timing['event'] == 'offer viewed']['time'].iloc[0]

        # selecting the last time the offer was completed
        time_completed = offer_timing[offer_timing['event'] == 'offer completed']['time'].iloc[-1]

        if time_completed >= time_viewed:
            offers_leading_to_transaction.append(offer)

    return offers_leading_to_transaction


def transform_profile(df):
    """
    Transform profile features to be pluggable into a model
    Args:
        - profile dataframe with 'became_member_on' column as int YYYYMMDD
    Return:
        - profile dataframe with seniority feature measuring the difference
        between the date 'became_member_on' and the last day where a client
        has become a member
    """
    #transfrom into to date format
    df['became_member_on'] = df['became_member_on'].apply(
    lambda x: '/'.join([str(x)[:4], str(x)[4:6], str(x)[6:]])
    )

    df['became_member_on'] = pd.to_datetime(df['became_member_on'])

    ref_date = df['became_member_on'].max()
    df['seniority'] = df['became_member_on'].apply(lambda x:(ref_date - x).days)

    return df

def main():

    print('Loading the data')
    portfolio, profile, transcript = load_data()

    print('Clean Transcript')
    transcript = transform_transcript(transcript)

    print('Focus on transactions led by offers, it can take a few minutes')
    offers_leading_to_transaction = get_transaction_from_offer(transcript[:10])

    # look at offers leading to buy
    types_leading_to_buy = transcript[
        transcript['personvalue'].isin(offers_leading_to_transaction)
    ]['value'].value_counts(normalize=True).reset_index()

    types_leading_to_buy.columns = ['id', 'share_of_transactions']

    types_leading_to_buy = portfolio.merge(types_leading_to_buy,
                                           on='id',
                                           how='outer').sort_values(by='share_of_transactions',
                                                                    ascending=False)
    # name the different offer based on their ranking
    types_leading_to_buy['offer_name'] = [
            'discount_1',
            'discount_2',
            'bogo_1',
            'bogo_2',
            'bogo_3',
            'bogo_4',
            'discount_3',
            'discount_4',
            'informational',
            'informational'
    ]

    focus_transcript = transcript[(transcript['personvalue'].isin(offers_leading_to_transaction))
                                & (transcript['event'] == 'offer completed')]
    print('Fetch associated profile info')
    # adding the offer name on the focus events
    offers_and_persons = focus_transcript[['person', 'value']].merge(types_leading_to_buy[['id', 'offer_name']],
                                                                     how='left',
                                                                     left_on='value',
                                                                     right_on='id')

    offers_and_persons = offers_and_persons.drop(['id', 'value'], axis=1)

    # adding the person info on the focus events
    offers_and_persons = offers_and_persons.merge(profile, how='left', left_on='person', right_on='id')

    # arranging the become_a_member info
    offers_and_persons = transform_profile(offers_and_persons)

    print('Keep useful variable for model and transform them')
    df = offers_and_persons[['offer_name', 'gender', 'age', 'income', 'seniority']]

    # one hot encode the gender variable
    df = pd.concat([df.drop('gender', axis=1),
                    pd.get_dummies(df['gender'], prefix='gender', prefix_sep='_', drop_first=True)],
                    axis=1,
                    sort=False)

    print('Saving the data in the data directory')
    # save dataframe df
    df.to_csv('data/clean_data.csv')


if __name__ == '__main__':
    main()
