"""Example webscrapping script."""
from mywebscrapper.contextmanager import MyDriverContextManager
from mywebscrapper.webscrapper import MyWebscrapper

def main():
    """Main function"""
    my_driver_context_manager = MyDriverContextManager()
    my_webscrapper = MyWebscrapper(
        driver_context_manager=my_driver_context_manager
    )
    report = my_webscrapper.start_scraping()
    print(report)

if __name__ == '__main__':
    main()