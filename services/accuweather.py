#!/usr/local/bin/python

import requests
import sys
import time
import yaml

from home_assistant import HomeAssistant

class Accuweather:
    FORECAST_API = 'http://dataservice.accuweather.com/forecasts'
    API_VERSION = '/v1'
    FORECAST_TYPE = '/daily/5day'
    SEVERITY_MAP = [
        'an unkown',
        'an extreme',
        'a major',
        'a moderate',
        'a minor',
        'a very Minor',
        'an insignificant',
        'a'
    ]
    DEFAULT_CATEGORY = 'event'
    QUOTA_EXCEEDED_MESSAGE = \
        "<phoneme rate='fast' pitch='-4st'>I'm so sorry</phoneme>. " + \
        "Your Accuweather API Key has exceeded the quota for today."

    def __init__(self, location_key, secrets_path):
        secrets = yaml.safe_load(open(secrets_path))
        self._accuweather_api_key = secrets['accuweather_api_key']
        self._location_key = location_key

    def _get_weather_data(self):
        query_args = f'apikey={self._accuweather_api_key}&language=en-us&details=true'
        response = requests.get(f'{self.FORECAST_API}{self.API_VERSION}{self.FORECAST_TYPE}/{self._location_key}?{query_args}')
        response.raise_for_status()
        return response.json()

    def _rate_limit_exceeded(self, data):
        return all([
            'Code' in data and data['Code'] == 'ServiceUnavailable',
            'Message' in data,
            data.get('Message', '') == 'The allowed number of requests has been exceeded.'
        ])
    
    def _get_min_and_max_temp_phrase(self, data):
        return f"a low of {round(data['Temperature']['Minimum']['Value'])}"
        + f" and a high of {round(data['Temperature']['Maximum']['Value'])}"

    def _format_forecast(self, data):
        if self._rate_limit_exceeded(data):
            # Exceeded the quota for today
            return self.QUOTA_EXCEEDED_MESSAGE
        else:
            # This script assumes the api won't change, so there won't be
            # any .get calls and all keys are expected to exist

            # If the sun has not set yet, get the day and night forecast.
            # Otherwise, get the night and tomorrow's day forecast
            today_forecast = data['DailyForecasts'][0]

            # Get the minimum and maximum temperatures for today
            todays_temp = self._get_min_and_max_temp_phrase(today_forecast)

            # If the it is before sunset, assume that we want the daytime forecast as well
            # as the nighttime forecast.
            if time.time() < today_forecast['Sun']['EpochSet']:
                message = f"Today's temperature is {todays_temp}"
                message += f" and today is {today_forecast['Day']['LongPhrase']}"
                message += f" and tonight is {today_forecast['Night']['LongPhrase']}."
            else:
                tomorrow_forecast = data['DailyForecasts'][1]
                tom_temp = self._get_min_and_max_temp_phrase(tomorrow_forecast)
                message = f"Today's temperature has been {tom_temp}."
                message += f" Tonight is {today_forecast['Night']['LongPhrase']},"
                message += f" tomorrow's temperature has {tom_temp},"
                message += f" and it will be {tomorrow_forecast['Day']['LongPhrase']}."

            # check the headline severity. If 1 <= severity <= 3 then add headline string onto the end of the forecast
            # 0 = Unknown
            # 1 = Significant
            # 2 = Major
            # 3 = Moderate
            # 4 = Minor
            # 5 = Minimal
            # 6 = Insignificant
            # 7 = Informational
            if 1 <= data['Headline']['Severity'] <= 3:
                category = data['Headline']['Category']
                severity_string = SEVERITY_MAP[data['Headline']['Severity']]
                message += f" There is {severity_string} {category} in the headline with "
                message += data['Headline']['Text'] + "."

            return message
    
    def get_forecast(self):
        return f'<speak>{self._format_forecast(self._get_weather_data())}</speak>'


if __name__ == "__main__":
    forecast = Accuweather(
        location_key=sys.argv[1],
        secrets_path='secrets.yaml'
    ).get_forecast()
    print(forecast)
    HomeAssistant(secrets_path='secrets.yaml').act(
        action='/services/script/turn_on',
        data={
            "entity_id": "script.alert_on_master_bedroom_display",
            "variables": {"message": forecast}
        }
    )
