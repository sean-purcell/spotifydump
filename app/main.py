import argparse
import logging
import os
import requests
import sys
import ujson

logger = logging.getLogger('sdump')

def parse_args():
    parser = argparse.ArgumentParser(description='Scrape spotify playlist')
    parser.add_argument('--client_id', type=str, default=os.getenv('CLIENT_ID'))
    parser.add_argument('--client_secret', type=str, default=os.getenv('CLIENT_SECRET'))
    parser.add_argument('--refresh_token', type=str, default=os.getenv('REFRESH_TOKEN'))
    parser.add_argument('--playlist', type=str, default=os.getenv('PLAYLIST'))
    parser.add_argument('--outpath', type=str, default=os.getenv('OUT_PATH'))
    parser.add_argument('--debug', default=os.getenv('DEBUG'), action='store_true')

    args = parser.parse_args()

    for arg in ['client_id', 'client_secret', 'refresh_token', 'playlist', 'outpath']:
        if not getattr(args, arg):
            raise ValueError('Arg missing: %s' % arg)

    return args

def setup_logging(args):
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

def get_auth_token(args):
    refresh_token = args.refresh_token
    client_id = args.client_id
    client_secret = args.client_secret
    if not refresh_token or not client_id or not client_secret:
        raise ValueError('authorization tokens must be provided')

    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    }
    result = requests.post('https://accounts.spotify.com/api/token', data=payload)
    if result.status_code != 200:
        raise Exception('Failed to get access token: %s' % result.text)
    data = ujson.loads(result.text)
    access_token = data['access_token']
    logger.debug('Obtained access token: %s', access_token)

    return access_token

def get_user_id(token):
    result = requests.get('https://api.spotify.com/v1/me',
            headers={'Authorization': 'Bearer %s' % token})
    if result.status_code != 200:
        raise Exception('Failed to get user id: %s' % result.text)
    data = ujson.loads(result.text)
    uid = data['id']
    logger.debug('User id is %s', uid)

    return uid

def get_playlist(name, token):
    offset = 0
    while True:
        result = requests.get('https://api.spotify.com/v1/me/playlists',
            params={'offset': offset, 'limit': 50},
            headers={'Authorization': 'Bearer %s' % token})
        if result.status_code != 200:
            raise Exception('Failed to enumerate playlists: %s' % result.text)
        data = ujson.loads(result.text)
        for playlist in data['items']:
            if playlist['name'] == name:
                pid = playlist['id']
                logger.debug('Playlist %s found with id %s', name, pid)
                return playlist['tracks']['href']
        offset += len(data['items'])
        if offset == data['total']:
            break

    raise Exception('Playlist %s not found', name)

def get_tracklist(tracks_url, token):
    tracks = []
    offset = 0
    while True:
        result = requests.get(tracks_url,
            params={'offset': offset, 'limit': 100},
            headers={'Authorization': 'Bearer %s' % token})
        if result.status_code != 200:
            raise Exception('Failed to enumerate playlist tracks: %s', result.text)
        data = ujson.loads(result.text)
        tracks += [
            {
                'name': track['track']['name'],
                'artist': track['track']['artists'][0]['name'],
            } for track in data['items']
        ]
        offset += len(data['items'])
        if offset == data['total']:
            break
    return tracks

def scrape_playlist(args):
    token = get_auth_token(args)
    tracks_url = get_playlist(args.playlist, token)
    tracks = get_tracklist(tracks_url, token)

    logger.debug('Dumping %s tracks to %s', len(tracks), args.outpath)

    with open(args.outpath, 'w') as outfile:
        for track in tracks:
            outfile.write('%s %s\n' % (track['name'], track['artist']))

def main():
    args = parse_args()
    setup_logging(args)

    logger.debug('Running with args %s', args)

    scrape_playlist(args)


if __name__ == '__main__':
    main()
