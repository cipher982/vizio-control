# vizio-control

Local network control for Vizio SmartCast TVs. Simple API for automation + web UI for manual control.

## Setup

```bash
# Copy and edit config
cp config.example.json config.json
# Add your TV's IP and pair to get auth_token

# Install and run
make install
make run

# Open http://localhost:8080
```

## Pairing a TV

1. Add TV to `config.json` with IP address (leave `auth_token` null)
2. Start the server
3. Click "pair" in the UI, enter the PIN shown on TV
4. Token is saved automatically

## API

All endpoints documented at `/docs` (OpenAPI).

Quick reference:
```bash
TV=bedroom

# Power
curl -X POST localhost:8080/api/tvs/$TV/power/on
curl -X POST localhost:8080/api/tvs/$TV/power/off

# Volume
curl -X POST localhost:8080/api/tvs/$TV/volume/up
curl -X POST localhost:8080/api/tvs/$TV/volume/down
curl -X POST localhost:8080/api/tvs/$TV/mute/toggle

# Navigation
curl -X POST localhost:8080/api/tvs/$TV/nav/up
curl -X POST localhost:8080/api/tvs/$TV/nav/ok
curl -X POST localhost:8080/api/tvs/$TV/nav/back
curl -X POST localhost:8080/api/tvs/$TV/nav/home

# Picture
curl -X POST localhost:8080/api/tvs/$TV/picture/backlight \
  -H "Content-Type: application/json" -d '{"value": 30}'

# Inputs
curl localhost:8080/api/tvs/$TV/inputs
curl -X POST localhost:8080/api/tvs/$TV/input \
  -H "Content-Type: application/json" -d '{"input_name": "HDMI-1"}'
```

## Docker

```bash
make docker
# or
docker compose up -d
```

Uses `network_mode: host` to reach TVs on local network.
