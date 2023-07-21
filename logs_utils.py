import logging

logger = logging.getLogger("pdf_gpt")
logger.setLevel(logging.DEBUG) 
logger.handlers = []

# Create handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler('logs/file.log')
c_handler.setLevel(logging.INFO)
f_handler.setLevel(logging.INFO)

# Create formatters and add it to handlers
c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)


# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)