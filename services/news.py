import requests
import time
import yaml

from bs4 import BeautifulSoup
from home_assistant import HomeAssistant


class NewsParser:
    NEWS_TIMEOUT = 60  # seconds

    def get(self, rss_feed):
        # Get RSS feed
        raw = requests.get(rss_feed)
        raw.raise_for_status()

        # Parse for the stream link
        soup = BeautifulSoup(raw.text)
        for i in range(self.NEWS_TIMEOUT):
            if soup.find('enclosure'):
                link = soup.find('enclosure').attrs['url']
                break
            print(f"Failed to parse RSS feed for link: {i}/{self.NEWS_TIMEOUT}")
            time.sleep(1)
        else:
            # Error
            raise Exception("Could not find media link for News within RSS feed.")
        
        duration = int(soup.find('itunes:duration').text)
        return link, f'{duration // 60} minutes and {duration % 60} seconds'

class NewsController:
    def __init__(self, home_assistant, news_parser, speaker, media_sources):
        self._home_assistant = home_assistant
        self._news_parser = news_parser
        self._speaker = speaker
        self._media_sources = media_sources

    def get_speaker_state(self):
        data = self._home_assistant.get(action=f'/states/{self._speaker}')

        for i in range(5):
            if data:
                break
            time.sleep(1)
        
        return data

    def wait_for_speaker(self, playing=False):
        # To avoid race condition, poll every 1 second for 10 seconds
        for i in range(10):
            data = self.get_speaker_state()
            state = data.get('state', 'UNKNOWN_STATE')
            print(f"Waiting for state to be {'playing' if playing else 'not playing'}; Current state: {state}")
            if (not playing and data.get('state', '') != 'playing') or (playing and data.get('state', '') == 'playing'):
                break
            state = data.get('state', 'UNKNOWN_STATE')
            print(f"Expected state to be {'playing' if playing else 'not playing'}; got {state}")
            time.sleep(1)
        else:
            raise Exception(f"Timed out waiting to play next media source")
        
        if data.get('state', '') == 'off':
            # Likely i stopped it with "Hey google stop"
            print("Stopping early since media source prematurely turned off")
            return False
        
        print(f"Successfully waited: State is {'' if playing else 'not '}playing")
        return True

    def play_and_wait(self, data):
        speaker_data = self._home_assistant.act(**data)

        # wait to allow speaker to begin playing the message
        if not self.wait_for_speaker(playing=True):
            return False
        speaker_data = self.get_speaker_state()

        # Sleep for the length of the content
        time.sleep(speaker_data.get('attributes', {}).get('media_duration', -1) + 1)

        if not self.wait_for_speaker():
            return False
        return True

    def play(self):
        for name, source in self._media_sources.items():
            url, length = self._news_parser.get(source)
            print(f"Playing preface for media: {name}")
            if not self.play_and_wait(
                    data={
                        'action': '/services/script/turn_on',
                        'data': {
                            "entity_id": "script.alert_on_master_bedroom_display",
                            "variables": {
                                "message": f"<speak>Here is your {name} update, it's {length}.</speak>",
                                "media_player": self._speaker}
                        }
                    }
                ):
                break
            print(f"Playing media: {name}")
            if not self.play_and_wait(
                    data={
                        'action': '/services/media_player/play_media',
                        'data': {
                            "entity_id": [self._speaker],
                            "media_content_id": url,
                            "media_content_type": "audio/mpeg"
                        }
                    }
                ):
                break

if __name__ == "__main__":
    np = NewsParser()
    ha = HomeAssistant(secrets_path='secrets.yaml')
    controller = NewsController(
        home_assistant=ha,
        news_parser=np,
        speaker='media_player.master_bathroom_speaker',
        media_sources={
            'ABC News': 'https://feeds.megaphone.fm/ESP9792844572',
            'WRAL News': 'https://feeds.megaphone.fm/wralnewsdaily',
            'NPR News': 'https://feeds.npr.org/500005/podcast.xml'
        }
    )
    controller.play()
