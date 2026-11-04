"""Shared Mac update-channel configuration. Contains public metadata only."""
import base64
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def release_base_url(config):
    repository = config.get('release_repository', '')
    if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Expected a GitHub owner/repository for Mac releases')
    return 'https://github.com/' + repository


def validate_update_channel(config):
    base = release_base_url(config)
    channel = config.get('release_channel', 'stable')
    if channel not in ('stable', 'preview'):
        raise ValueError('Unknown release channel')
    expected = (f"https://raw.githubusercontent.com/{config['release_repository']}/main/updates/preview.xml"
                if channel == 'preview' else base + '/releases/latest/download/appcast.xml')
    if config.get('update_feed') != expected:
        raise ValueError('Mac update feed must match release_repository')
    validate_release_url(expected)
    try:
        key = base64.b64decode(config.get('update_public_key', ''), validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError('Expected a base64 Ed25519 public update key') from error
    if len(key) != 32:
        raise ValueError('Expected a 32-byte Ed25519 public update key')


def load_config():
    config = json.loads(Path(__file__).with_name('macos-release.json').read_text())
    validate_update_channel(config)
    return config


def validate_release_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Release URLs must use HTTPS without credentials')
    if parsed.hostname.lower() == 'github.com' and (
        parsed.path.lower().rstrip('/') == '/leozhang8654/yukio-desktop-pet'
        or parsed.path.lower().startswith('/leozhang8654/yukio-desktop-pet/')
    ):
        raise ValueError('Retired release URL: verify restored assets and regenerate the signed feed')


def apply_update_settings(info, config):
    validate_update_channel(config)
    info.update(SUFeedURL=config['update_feed'], SUPublicEDKey=config['update_public_key'],
                SURequireSignedFeed=True, SUVerifyUpdateBeforeExtraction=True)


if __name__ == '__main__':
    import argparse
    import plistlib
    parser = argparse.ArgumentParser(description='Apply the shared update channel before signing an App')
    parser.add_argument('plist', type=Path)
    args = parser.parse_args()
    info = plistlib.loads(args.plist.read_bytes())
    apply_update_settings(info, load_config())
    args.plist.write_bytes(plistlib.dumps(info))
