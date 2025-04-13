"""
Mock implementation of the FrontendServer module.
This is a placeholder to allow tests to run without the actual module.
"""

class FrontendServer:
    """Mock implementation of the FrontendServer class."""
    
    def __init__(self, host='localhost', port=8000, static_dir=None):
        self.host = host
        self.port = port
        self.static_dir = static_dir
        self.is_running = False
    
    def start(self):
        """Mock start method."""
        self.is_running = True
        return True
    
    def stop(self):
        """Mock stop method."""
        self.is_running = False
        return True
    
    def get_url(self):
        """Return the URL for the server."""
        return f"http://{self.host}:{self.port}"
