from typing import Annotated

from cyclopts import App, Parameter

from three_houses.scraper import ENDPOINTS, Scraper

app = App()


@app.command
def main(
    endpoints: Annotated[
        list[ENDPOINTS] | None,
        Parameter(help="Endpoints to scrape", consume_multiple=True, alias="endpoint"),
    ] = None,
    *,
    save: Annotated[bool, Parameter(help="Whether to save the data")] = True,
) -> None:
    Scraper(endpoints=endpoints).scrape(save=save)


if __name__ == "__main__":
    app()
