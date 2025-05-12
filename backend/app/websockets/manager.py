from app.websockets.connection_manager import ConnectionManager

# Create a global instance of the Connection Manager
# Both main.py and websockets/routes.py will import this instance
ws_manager = ConnectionManager() 