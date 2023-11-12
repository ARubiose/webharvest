
from webharvest import Webscrapper

from mywebscrapper.states import InitialState, FinalState

class MyWebscrapper(Webscrapper):
    """MyWebscrapper class"""

    @property
    def initial_state(self):
        return InitialState
