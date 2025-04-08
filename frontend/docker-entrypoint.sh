#!/bin/sh
# Exit immediately if a command exits with a non-zero status.
set -e

# Define the directory where your built JS files are served by Nginx
HTML_ROOT_DIR="/usr/share/nginx/html"
# Often Vite puts JS into an 'assets' subdirectory, adjust if needed
JS_ASSETS_DIR="$HTML_ROOT_DIR/assets"

# --- Define the EXACT placeholder strings used during the build ---
PLACEHOLDER_API_URL="__VITE_API_BASE_URL_PLACEHOLDER__"
PLACEHOLDER_WS_URL="__VITE_WEBSOCKET_URL_PLACEHOLDER__"

# --- Read the ACTUAL URLs from Koyeb Runtime Environment Variables ---
# IMPORTANT: Use the variable names EXACTLY as defined in your Koyeb Service Environment Variables.
# Check your Koyeb dashboard. These are EXAMPLES - replace if necessary.
ACTUAL_API_URL="${API_BASE_URL}"
ACTUAL_WS_URL="${WEBSOCKET_URL}"

# Check if variables are set (optional but recommended)
if [ -z "$ACTUAL_API_URL" ]; then
  echo "Error: Environment variable API_BASE_URL is not set."
  exit 1
fi
if [ -z "$ACTUAL_WS_URL" ]; then
  echo "Error: Environment variable WEBSOCKET_URL is not set."
  exit 1
fi

echo "Runtime Configuration:"
echo "Replacing '$PLACEHOLDER_API_URL' with '$ACTUAL_API_URL'"
echo "Replacing '$PLACEHOLDER_WS_URL' with '$ACTUAL_WS_URL'"

# Escape special characters (like /) in the actual URLs for sed
ACTUAL_API_URL_ESC=$(echo "$ACTUAL_API_URL" | sed 's/[\/&]/\\&/g')
ACTUAL_WS_URL_ESC=$(echo "$ACTUAL_WS_URL" | sed 's/[\/&]/\\&/g')

# Find all Javascript files within the assets directory (or HTML_ROOT_DIR if no assets)
# Use -print0 and xargs -0 for safety with filenames containing spaces/special chars
find "$JS_ASSETS_DIR" -type f -name '*.js' -print0 | xargs -0 sed -i \
    -e "s/${PLACEHOLDER_API_URL}/${ACTUAL_API_URL_ESC}/g" \
    -e "s/${PLACEHOLDER_WS_URL}/${ACTUAL_WS_URL_ESC}/g"

echo "Variable substitution complete. Starting Nginx..."

# Execute the command passed as arguments to this script (which is the CMD from Dockerfile)
exec "$@"