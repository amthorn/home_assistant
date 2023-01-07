
import requests
import yaml


class HomeAssistant:
    HOST = 'http://localhost:8123'
    API = '/api'
    HEADERS = {
        "content-type": "application/json",
    }

    def __init__(self, secrets_path):
        secrets = yaml.safe_load(open(secrets_path))
        self._homeassistant_api_key = secrets['homeassistant_api_key']
    
    def _call(self, method, action, data):
        print("Calling home assistant")
        response = requests.request(method=method, url=f'{self.HOST}{self.API}{action}', headers={
            **self.HEADERS,
            "Authorization": f"Bearer {self._homeassistant_api_key}",
        }, json=data)
        response.raise_for_status()
        return response.json()

    def act(self, action, data={}):
        return self._call('POST', action, data)

    def get(self, action, data={}):
        return self._call('GET', action, data)
