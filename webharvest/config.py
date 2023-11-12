"""Package configuration."""
import pathlib
import configparser

ROOT_DIR = pathlib.Path(__file__).parents[1]
CONFIG_DIR = ROOT_DIR / 'config'
DOWNLOAD_DIR = ROOT_DIR / 'downloads'
SCREENSHOT_DIR = ROOT_DIR / 'screenshots'
LOGS_DIR = ROOT_DIR / 'logs'

def get_config( config_file:str = 'config.ini' ) -> configparser.ConfigParser:
    """Get configuration from config.ini file.
    
    Returns:
        configparser.ConfigParser: Config file
    """
    # Config file path
    config_path = ROOT_DIR / config_file
    # Config parser
    config = configparser.ConfigParser() 
    # Read config file
    config.read(config_path)
    # Return config
    return config 

def get_download_directory() -> str:
    """Get download directory."""
    config = get_config()
    return config.get(section='PATHS', option='DOWNLOAD_DIR', fallback=str(DOWNLOAD_DIR))

def get_screenshot_directory() -> str:
    """Get screenshot directory."""
    config = get_config()
    return config.get(section='PATHS', option='SCREENSHOT_DIR', fallback=str(SCREENSHOT_DIR))
