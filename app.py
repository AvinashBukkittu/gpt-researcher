"""Backend logic for GPT Researcher
"""
import os
import logging
import openai

from flask import Flask, redirect, render_template, request, url_for  # type: ignore
from flask_sse import sse  # type:ignore
from utils import extract_content_from_urls, generate_summary_prompts, generate_summary, query_bing

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
app.config["REDIS_URL"] = "redis://localhost"
app.register_blueprint(sse, url_prefix='/stream')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FINAL_SUMMARY = """
ChatGPT is an AI chatbot developed by OpenAI that is built on the GPT-3 language model. It has been trained on a massive amount of text data, including books, articles, websites, and social media. This extensive training allows ChatGPT to generate human-like responses to text prompts. It has gained popularity and reached 100 million users in just two months due to its ability to create accurate and diverse responses, including essays, articles, and poetry. However, it also has limitations, as its responses can sometimes be inaccurate or misleading. OpenAI has now released its next-generation GPT-4 models, which offer improved capabilities. GPT-4 can better understand context and produce more accurate and relevant language. It is also more capable of handling multiple tasks simultaneously. OpenAI has focused on ensuring the safety of GPT-4 by implementing a monitoring framework and consulting with experts in various fields. ChatGPT offers a free tier, but OpenAI has introduced a subscription-based ChatGPT Plus plan that provides benefits such as uninterrupted access during peak times, faster response times, and priority access to new features. OpenAI has expressed its intention to continue offering free access to ChatGPT, but the long-term availability of the free tier is uncertain. ChatGPT has been found to be useful for various language-based tasks, including translations, learning new languages, generating job descriptions, and creating meal plans. GPT-4 builds on these capabilities and aims to provide more accurate and fact-based responses. The development of GPT-4 represents an important step towards AI-powered chatbots and applications that prioritize accuracy and reliability. ChatGPT is a natural language processing tool developed by OpenAI. It allows users to have human-like conversations and perform various tasks such as composing emails, essays, and code. The language model can answer questions and assist users with their queries. While the basic version of ChatGPT is free to use, there is also a subscription option available for $20/month that offers additional perks like general access even at capacity, access to GPT-4, faster response times, and internet access through plugins. However, the free version still provides similar technical abilities, except for access to the latest version of the large language model (GPT-4) and the internet. ChatGPT has gained popularity, but the server may face overload during peak times. The chatbot has limitations in terms of specific question wording and the quality of responses it delivers. It also lacks awareness of events and news beyond 2021 and does not provide sources for its responses. Concerns have been raised about AI chatbots replacing human intelligence, spreading misinformation, and potential misuse by students to cheat. The Federal Trade Commission is investigating OpenAI regarding data collection, misinformation, and risk assessment. GPT-4 is the latest version of OpenAI's language model and offers improved capabilities, including accepting text and image inputs. Microsoft's Bing Chat runs on GPT-4 and provides more efficiency and internet access compared to the free version of ChatGPT. Google's Bard is another AI language model but falls short in answering questions compared to ChatGPT. ChatGPT is an AI chatbot developed by OpenAI that utilizes the Generative Pre-trained Transformer (GPT) model. It takes a piece of text and predicts the next token in the sequence, adjusting its parameters through training to improve its accuracy. ChatGPT Plus is the paid version, offering priority responses, customer support, and is based on the more advanced GPT-4 model. It can be accessed through OpenAI's API, with payment based on the number of tokens used. ChatGPT has various applications such as generating written content, summarizing documents, answering questions, and acting as a tutor or planning assistant. It has some limitations and competing models have been developed by other companies. ChatGPT-3.5 is the version powering the free research preview of ChatGPT, while ChatGPT-4 is the upgraded version with more capabilities. The ChatGPT API allows developers to integrate ChatGPT into their own apps. ChatGPT has received positive feedback as a writing assistant, offering suggestions for word choices, generating ideas, providing accurate information, suggesting fictional names, and reviewing and editing writing. However, it is important to verify information from ChatGPT with other sources and maintain a balance between accepting its suggestions and retaining creative control. ChatGPT for Android is now available, according to The Verge. The language model has gained significant attention for its success, although its future remains uncertain after the launch of Threads. ChatGPT has been widely regarded as a groundbreaking development in natural language processing and artificial intelligence. Developed by OpenAI, it has showcased impressive capabilities in generating human-like responses to text prompts. However, the recent launch of Threads, another AI-powered chat app, has raised questions about the continued success of ChatGPT. It is unclear whether the hype surrounding ChatGPT will persist or if it has reached a plateau. The Verge refers to ChatGPT as the "poster child for explosive success," suggesting that it has garnered considerable attention and acclaim. The Verge is a part of the Vox Media network and provides news and analysis on various topics, including technology. The availability of ChatGPT for Android expands its accessibility to a wider user base, potentially increasing its reach and impact. Overall, while ChatGPT has experienced significant success, its future trajectory remains uncertain due to the introduction of competing AI chat apps like Threads. It will be interesting to see how ChatGPT evolves and whether it can maintain its position as a leading language model in the field of natural language processing.
"""

@app.route("/", methods=("GET", "POST"))
def index():
    r"""API endpoint for GPT-Researcher.

    It accepts both GET and POST requests. On submitting the form, this method
    searches the web for top results, extracts contents from web pages and summarizes the result.
    """
    if request.method == "POST":
        query = request.form["query"]

        # search the web for relevant results
        logger.info("Searching the web")
        sse.publish({"message": "Searching the web", "percentage": "2"}, type='status_update')
        urls = query_bing(query=query)


        # extract the contents from the top-k documents
        logger.info("Extracting contents from the top results")
        sse.publish(
            {"message": "Extracting contents from the top results", "percentage": "33"},
            type='status_update'
        )
        contents = extract_content_from_urls(query=query, urls=urls)

        sse.publish(
            {"message": "Generating prompts", "percentage": "50"},
            type='status_update'
        )
        prompts = generate_summary_prompts(query=query, contents=contents)

        # Summarize the results using LLM models
        logger.info("Summarizing the results")
        sse.publish(
            {"message": "Summarizing the results", "percentage": "66"},
            type='status_update'
        )
        summary = generate_summary(query, prompts)

        sse.publish({"message": "Complete!", "percentage": "100"}, type='status_update')
        return redirect(url_for("index", status="Complete!", result=summary))

    result = request.args.get("result")
    return render_template("index.html", result=result)
