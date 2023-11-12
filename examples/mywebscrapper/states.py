from webharvest import DriverState, ContextStatusEnum

from mywebscrapper.schemas import InputData, OutputData

class MyDriverState(DriverState[InputData, OutputData]):
    """MyDriverState class"""

class InitialState(MyDriverState):
    """Initial state class"""

    GOOGLE_URL = 'https://www.google.com/'

    def run(self):
        self.driver.get(f'{self.GOOGLE_URL}/search?q={self.input.search_item}')
        self.driver_context.set_state(FinalState)


class FinalState(MyDriverState):
    """Final state class"""

    def run(self):
        self.output.data = self.driver.page_source
        self.set_run_status(ContextStatusEnum.SUCCEED)