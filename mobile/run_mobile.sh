#!/bin/bash
# Try to set the limit as high as possible
ulimit -n 65536 2>/dev/null || ulimit -n 10240

echo "Current limit:"
ulimit -n

echo "Starting Expo (clearing cache)..."
npx expo start --clear
