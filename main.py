"""CLI tool for GPT Researcher."""

import logging
import sys
import argparse


from utils import extract_content_from_urls, generate_summary_prompts, generate_summary, query_bing


logging.basicConfig(level=logging.INFO)

# Create a custom logger
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("-q", "--query", help="query to search the web and summarize the results for")

class BColors:  # pylint: disable=too-few-public-methods
    r"""Class for terminal colors."""

    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

if __name__ == "__main__":
    args = parser.parse_args()
    if len(sys.argv) != 3:
        parser.print_help()
        sys.exit()

    query = args.query

    # search the web
    logger.info("%s Searching the web %s",BColors.OKGREEN, BColors.ENDC)
    urls = query_bing(query=query)

    # extract the contents from the urls
    logger.info("%s Extracting contents from the top results %s", BColors.OKGREEN, BColors.ENDC)
    contents = extract_content_from_urls(query=query, urls=urls)

    logger.info("%s Generating prompts %s", BColors.OKGREEN, BColors.ENDC)
    prompts = generate_summary_prompts(query=query, contents=contents)

    # summarize the results
    logger.info("%s Summarizing the results %s", BColors.OKGREEN, BColors.ENDC)
    summary = generate_summary(query, prompts)

    print(BColors.OKBLUE + summary + BColors.ENDC)
