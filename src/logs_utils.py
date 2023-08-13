import logging

logger = logging.getLogger("async_gpt")
logger.setLevel(logging.DEBUG)
logger.handlers = []

# Create handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler("logs/file.log")
c_handler.setLevel(logging.INFO)
f_handler.setLevel(logging.INFO)

# Create formatters and add it to handlers
c_format = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
f_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)


# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)


class ExceptionStats:
    """Stores information about all occured exceptions.

    - Group exceptions by their type.
    - Count exceptions of each type
    - Store one exceptions instances for each exceptions type
    """

    def __init__(self):
        self._data = dict()

    def add_exception(self, ex: Exception):
        ex_type = type(ex)
        if ex_type in self._data:
            self._data[ex_type]["count"] += 1
        else:
            self._data[ex_type] = {}
            self._data[ex_type]["count"] = 1
            self._data[ex_type]["ex"] = ex

    def print_stats(self):
        if len(self._data) == 0:
            logger.info(f"No stats on exception collected")

        for err_type in self._data:
            ex_cnt = self._data[err_type]["count"]
            exception = self._data[err_type]["ex"]
            logger.info(
                f"Got {ex_cnt} exceptions with type {type(exception)}, msg example: {exception}"
            )
