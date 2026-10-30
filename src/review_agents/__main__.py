import logging

import uvicorn

from review_agents.api import create_app
from review_agents.config import Settings


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
