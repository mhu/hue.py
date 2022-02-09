#!/usr/bin/python3

import math
import random
import requests
import sys
import yaml
from typing import Dict, List, Tuple, Union

CONFIG_FILEPATH = './.huerc'
config = {}

# Methods enhance_color and rgb_to_xyz from: https://gist.github.com/error454/6b94c46d1f7512ffe5ee

def enhance_color(normalized: float) -> float:
    if normalized > 0.04045:
        return math.pow((normalized + 0.055) / (1.0 + 0.055), 2.4)
    else:
        return normalized / 12.92


def rgb_to_xy(rgb: Tuple[int, int, int]) -> Tuple[float, float]:
    r, g, b = rgb

    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    r_final = enhance_color(r_norm)
    g_final = enhance_color(g_norm)
    b_final = enhance_color(b_norm)

    x = r_final * 0.649926 + g_final * 0.103455 + b_final * 0.197109
    y = r_final * 0.234327 + g_final * 0.743075 + b_final * 0.022598
    z = r_final * 0.000000 + g_final * 0.053077 + b_final * 1.035763

    if x + y + z == 0:
        return (0, 0)
    else:
        x_final = x / (x + y + z)
        y_final = y / (x + y + z)

        return (x_final, y_final)


def get_cli_args() -> Dict[str, Union[str, List[str]]]:
    if len(sys.argv) == 1 or sys.argv[1] == 'help':
        filename = sys.argv[0].split('/').pop()
        print('Usage:')
        print(filename + ' help')
        print(filename + ' setup')
        print(filename + ' list')
        print(filename + ' <device-id> on|off')
        print(filename + ' <device-id> brightness <0-255>')
        print(filename + ' <device-id> color <color>')
        print(filename + ' <device-id> color <r> <g> <b>')
        print(filename + ' <device-id> color random')
        sys.exit()

    if sys.argv[1] == 'list':
        devices = get_known_devices()

        for device_id, information in devices.items():
            state = information['state']

            on_status = 'on' if state['on'] else 'off'
            print(f'Device {device_id} ({on_status})')

            name = information['productname']
            print('# Name: ' + name)

            brightness = state['bri']
            print('# Brightness: ' + str(brightness))

        sys.exit()

    if sys.argv[1] == 'setup':
        if 'bridge_url' not in config:
            create_bridge_url()

        if 'user' not in config:
            create_user()

        sys.exit()

    if not sys.argv[1].isnumeric():
        sys.exit('Wrong format for device')

    return {
        'device': sys.argv[1],
        'options': sys.argv[2:]
    }


def get_known_devices() -> Dict:
    global config

    url = config['bridge_url']
    user = config['user']
    response = requests.get(url + '/api/' + user + '/lights')

    return response.json()


def save_config(field: str, value) -> None:
    with open(CONFIG_FILEPATH, 'rw') as f:
        config = yaml.safe_load(f)
        config[field] = value
        yaml.dump(config, f)


def load_config() -> None:
    global config

    with open(CONFIG_FILEPATH, 'r') as f:
        config = yaml.safe_load(f)

    if config is None:
        config = {
            'bridge_url': 'http://philips-hue.fritz.box',
            'user': '9BPkuqCwCfuAHsoAXBf9fQVKZbhQ5uq3MyuOv8EF'
        }


def is_error_response(response: requests.Response) -> bool:
    first_response = response.json()[0]
    return 'error' in first_response


def create_bridge_url() -> None:
    global config

    print('No bridge URL configured.')

    bridge_url = input('Enter bridge URL: ')

    while not is_valid_bridge_url(bridge_url):
        print('Invalid bridge URL.')
        bridge_url = input('Try again: ')

    save_config('bridge_url', bridge_url)


def is_valid_bridge_url(url: str) -> bool:
    if not url.startswith('http://') and not url.startswith('https://'):
        url = f'http://{url}'

    if not url.endswith('/'):
        url += '/'

    try:
        response = requests.get(f'{url}api/newdeveloper')
        if response.status_code != 200:
            return False
        return response.json()[0]['error']['description'] == 'unauthorized user'
    except Exception:
        return False


def create_user() -> None:
    global config

    print('You have not created a user yet.')
    print('Creating user...')

    body = { "devicetype": "hue_py_app" }
    response = requests.post(config['bridge_url'] + '/api', json=body)

    while is_error_response(response):
        print('Press the link button on your hue bridge.')
        input('Press enter to continue.')
        response = requests.post(config['bridge_url'] + '/api', json=body)

    user = response.json()[0]['success']['username']
    save_config('user', user)

    print(f'Successfully created user! ({user})')

    return user


def get_api_url() -> str:
    global config

    url = config['bridge_url']
    user = config['user']

    return url + '/api/' + user


def toggle_light(id: str, state: str) -> requests.Response:
    if state != 'on' and state != 'off':
        return

    state = True if state == 'on' else False
    body = { 'on': state }

    api_url = get_api_url()
    return requests.put(api_url + '/lights/' + id + '/state', json=body)


def set_brightness(id: str, level: str) -> requests.Response:
    level = int(level)
    if level < 0 or level > 255:
        sys.exit('Brightness must be between 0 and 255')

    body = { 'bri': level }

    api_url = get_api_url()
    return requests.put(api_url + '/lights/' + id + '/state', json=body)


def get_rgb_for_color(color: str) -> Tuple[int, int, int]:
    colors = {
        'red': (255, 0, 0),
        'green': (0, 128, 0),
        'blue': (0, 0, 255),
        'lime': (0, 255, 0),
        'yellow': (255, 255, 0),
        'cyan': (0, 255, 255),
        'purple': (128, 0, 128)
    }

    if color == 'random':
        return random.choice(list(colors.values()))

    if color not in colors.keys():
        sys.exit('Unknown color')

    return colors[color]


def set_color(id: str, color) -> requests.Response:
    if type(color) is str:
        xy = rgb_to_xy(get_rgb_for_color(color))
    elif type(color) is list:
        xy = rgb_to_xy(
            tuple([
                int(color[0]),
                int(color[1]),
                int(color[2])
            ])
        )
    else:
        sys.exit('Color must be a color or rgb values')

    body = { 'xy': xy }

    api_url = get_api_url()
    return requests.put(api_url + '/lights/' + id + '/state', json=body)


def run_command(args: Dict) -> None:
    response = None

    if args['options'][0] == 'on' or args['options'][0] == 'off':
            response = toggle_light(args['device'], args['options'][0])

    elif args['options'][0] == 'brightness':
            response = set_brightness(args['device'], args['options'][1])

    elif args['options'][0] == 'color':
        if len(args['options']) == 2:
            response = set_color(args['device'], args['options'][1])
        else:
            response = set_color(args['device'], args['options'][1:])

    if response is not None and is_error_response(response):
        sys.exit('Operation failed: ' + response.json()[0]['error']['description'])


if __name__ == '__main__':
    load_config()
    args = get_cli_args()

    if 'bridge_url' not in config:
        create_bridge_url()

    if 'user' not in config:
        create_user()

    run_command(args)
