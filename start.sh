#!/bin/bash

# Start API server in background
python server.py &

# Start Telegram bot in foreground
python bot.py
