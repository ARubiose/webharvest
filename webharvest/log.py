"""Module for logging"""
import os
import logging

from webharvest import config

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(name)s %(levelname)s: %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(os.path.join(config.LOGS_DIR, 'webharvest.log')),
        logging.StreamHandler()
    ]
)


