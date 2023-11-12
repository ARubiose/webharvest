from typing import List
from webharvest import DriverContextManager, ContextStatusSchema

from mywebscrapper.schemas import InputData, OutputData

class MyDriverContextManager(DriverContextManager):
    """MyDriverContextManager class"""

    def generate_scraping_contexts(self) -> List[ContextStatusSchema]:
        return [self._create_dummy_context_status()]
    
    def _create_dummy_context_status(self) -> ContextStatusSchema:
        return ContextStatusSchema(
            input_data=InputData(search_item='python'),
            output_data=OutputData(),
        )
    
    def add_context_status(self, context_status: ContextStatusSchema) -> None:
        self.status_contexts.append(context_status)

    def stop_processing(self) -> None:
        output_data:OutputData = self.status_contexts[0].output_data
        page_source =  output_data.data

        with open('page_source.html', 'w', encoding='UTF-8') as file:
            file.write(page_source)

    def create_process_report(self) -> None:
        return 'Success'
    

        