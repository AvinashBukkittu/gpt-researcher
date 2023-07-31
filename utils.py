"""This file provide utility functions for GPT-Researcher."""

from typing import List, Optional, Tuple
import os
import logging
from multiprocessing import Pool
import requests

from bs4 import BeautifulSoup
import openai


# Create a custom logger
logger = logging.getLogger(__name__)

# below is the approximate relationship between tokens, characters and words
# READ: https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
CHARACTER = 1
NUM_OF_CHARACTERS_IN_A_TOKEN = 4 * CHARACTER  # 1 token ~ 4 characters

# we assume avg query + prompt length to be 250 tokens
AVG_PROMPT_TOKEN_LENGTH = 250

# we assume that we summarize the results in 200 words (~ 250 tokens)
AVG_SUMMARY_TOKEN_LENGTH = 250

# we assume we use LLM models with max context length of 4k tokens
# therefore max webpage content length is given below
MAX_WEBPAGE_CONTENT_LENGTH = 4000 - AVG_PROMPT_TOKEN_LENGTH - AVG_SUMMARY_TOKEN_LENGTH
MAX_WEBPAGE_CONTENT_LENGTH_IN_CHARACTERS = NUM_OF_CHARACTERS_IN_A_TOKEN * MAX_WEBPAGE_CONTENT_LENGTH


ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

def query_bing(query: str, k=10) -> List[str]:
    """
    Queries Bing Search engine using the Bing Websearch API and returns the results.
    More information on this can be found at
    https://www.microsoft.com/en-us/bing/apis/bing-web-search-api

    Args:
         query (str): The query to search on the search engine
         k (int): Number of results to return (default to 10)

    Returns:
        urls (List[str]): A list of urls extracted from the search result

    Raises:
        (1) KeyError if BING_SEARCH_V7_SUBSCRIPTION_KEY is not set
        (2) Exception if the function is unable to fetch the results from Bing Search Engine
    """
    subscription_key = os.environ.get('BING_SEARCH_V7_SUBSCRIPTION_KEY', None)
    if subscription_key is None:
        raise KeyError("ENV variable, 'BING_SEARCH_V7_SUBSCRIPTION_KEY' is not set. \
            Please set a subscription key to search on the web.")

    # Construct a request
    mkt = 'en-US'
    params = {
        'q': query,
        'mkt': mkt,
        'count': k,
        'responseFilter': 'webpages'  # for now, focus on webpage results only
    }
    headers = {'Ocp-Apim-Subscription-Key': subscription_key}

    try:
        logger.info(f"Pulling webresults from endpoint, {ENDPOINT}")
        response = requests.get(ENDPOINT, headers=headers, params=params, timeout=180)
        response.raise_for_status()
        json_response = response.json()

        # extract webpages result
        urls = []
        for search_result in json_response["webPages"]["value"]:
            urls.append(search_result["url"])
        return urls
    except Exception as ex:
        logger.error(f"Failed while retrieving the results using Bing Websearch API, {ex}")
        raise ex


def extract_content_from_urls(query: str, urls: List[str]) -> List[str]:
    r"""Extract text content from the URLs. 

    Concatenates the results from the webpages until MAX_WEBPAGE_CONTENT_LENGTH_IN_CHARACTERS
    characters is reached. After that, a new entry is created. This is done to avoid exceeding
    the maximum context length supported by the model. Assumes a maximum of 4k tokens for the LLM.
    The logic below can be improved to support T max tokens.

    Args:
        query (str): The query issued by the user
        urls (List[str]): A list of URLs to extract contents from.

    Returns:
        contents (List[str]): List of contents extracted from relevant webpages
    """

    # parallelize the extraction of web contents across multiple processes
    pool = Pool(processes=len(urls))  # pylint: disable=consider-using-with
    url_contents = pool.map(extract_content_from_url, urls)
    pool.close()
    logger.info(f"Extracted contents from a total of {len(urls)} urls")

    contents = []
    curr_content = ""
    for text, title in url_contents:
        # if title is None, use the query as the title instead
        title = query if title is None else title

        # this means, we can add this url's text to the existing context
        # logic here can be improved to support T max tokens for AI model
        text_len = len(f"\n\n{title}\n\n") + len(text)
        if len(curr_content) + text_len < MAX_WEBPAGE_CONTENT_LENGTH_IN_CHARACTERS:
            curr_content += f"\n\n{title}\n\n" + text

        # this means by adding this url's text we will exceed the
        # max context length for the AI model, therefore, we will
        # create a new content and add it
        else:
            # if the first web content is too big,
            # then `curr_content` is empty
            if len(curr_content) > 0:
                contents.append(curr_content)

            # create a new content from the current url's text and title
            # if the text is too long, trim it to MAX_WEBPAGE_CONTENT_LENGTH_IN_CHARACTERS
            curr_content = f"\n\n{title}\n\n" + text
            curr_content = curr_content[:MAX_WEBPAGE_CONTENT_LENGTH_IN_CHARACTERS]

    contents.append(curr_content)

    logger.info(f"Total number of entries in 'contents'={len(contents)}")
    return contents


def extract_content_from_url(url: str) -> Tuple[str, Optional[str]]:
    r"""Extract content from a given URL.

    The logic currently focuses only on <p> tags and the <title> tags. 
    However, there is scope to improve the extraction logic.

    Args:
        url (str): Given URL string

    Returns:
        A tuple consisting of URL content and the title of the webpage
    """
    try:
        logger.info(f"Extracting contents from {url=}")
        url_content = requests.get(url, timeout=180)
        soup = BeautifulSoup(url_content.text, "html.parser")
        website_content = []
        p_tags = soup.find_all("p")
        # title = None
        # if soup.find("title"):
        #     title = soup.find("title").text

        title = soup.find("title").text if soup.find("title") else None  # type:ignore

        for p_tag in p_tags:
            if p_tag.text is not None:
                website_content.append(p_tag.text)  # for now, extract only <p> tags
        return ''.join(website_content), title
    except Exception as ex:  # pylint: disable=broad-exception-caught
        # error while parsing contents of url
        logger.warning(f"Exception raised while retrieving and parsing {url=}, {ex=}. \
            Returing empty strings.")
        return '', ''


def generate_summary_prompts(query: str, contents: List[str]) -> List[str]:
    r"""Generate summary prompts for a given `query` and `contents`

    Args:
        query (str): The query issued by the user
        contents (List[str]): List of contents extracted from the relevant webpages

    Returns
        prompts (List[str]): A list of prompts to be issued to an AI model
    """
    prompts = []
    for content in contents:
        prompt = generate_summary_prompt(query, content)
        prompts.append(prompt)
    return prompts


def generate_summary_prompt(query: str, content: str) -> str:
    r"""Generate summary prompt using the given `query` and `content`

    Args:
        query (str): The query issued by the user
        content (str): Content extracted from a webpage

    Returns:
        A prompt string which is supplied to LLM models for a response.
    """
    logger.info(f"Generating summary prompt for {query=}")
    prompt = f"""
    Below in triple quotes is the content extracted from the web for the query, '{query}'.
    
    ```
    {content}
    ```
    
    Summarize the web results in 200 words.
    """
    return prompt

def generate_summary_per_prompt(prompt: str) -> str:
    r"""Generate summary for a given prompt.

    This method uses OpenAI models to generate summary.

    Args:
        prompt (str): Given prompt

    Returns:
        summary (str): Summary generated by the LLM. 
            Returns empty string is exception is raised.
    """
    try:
        logger.info("Generating summary for a single prompt")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"{prompt}"}],
            temperature=0.6,
        )
        summary = response.choices[0].message.content
    except Exception as ex:  # pylint: disable=broad-exception-caught
        logger.warning(f"Error while generating summary for {prompt=}, {ex=}")
        summary = ""

    return summary


def generate_summary(query: str, prompts: List[str]) -> str:
    r"""Generate summary from the web search results using the `prompts`.

    Generate summary for each prompt in `prompts`. It then generates a final summary using the
    summary from each prompt.

    Args:
        query (str): Search query issued by the user.
        prompts (List[str]): A list of prompts used to summarize the results

    Returns:
        final_summary (str): A summary of results extracted from the web
    """
    logger.info(f"Summarizing results from prompts for {query=}")

    openai.api_key = os.getenv("OPENAI_API_KEY")
    if openai.api_key is None:
        raise KeyError("ENV variable 'OPENAI_API_KEY' is not set. \
            Please set this key before querying OpenAI APIs.")

    # parallelize summary generation across multiple processes
    pool = Pool(processes=len(prompts))  # pylint: disable=consider-using-with
    summaries = pool.map(generate_summary_per_prompt, prompts)
    pool.close()

    logger.info(f"Generated a total of {len(summaries)} summaries for the {query=}")

    if len(summaries) > 1:
        logger.info("Generating a final summary")
        # concatenate all the queries and truncate it max char length
        summaries_concatenated = '\n\n'.join(summaries)
        summaries_concatenated = summaries_concatenated[:MAX_WEBPAGE_CONTENT_LENGTH_IN_CHARACTERS]
        final_prompt = generate_summary_prompt(query=query, content=summaries_concatenated)
        final_summary = generate_summary_per_prompt(final_prompt)
    else:
        final_summary = summaries[0]
    return final_summary
