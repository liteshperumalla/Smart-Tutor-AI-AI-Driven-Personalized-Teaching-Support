import streamlit as st
from utils import render_footer # Assuming render_footer is in utils.py
import auth
auth.initialize_session()

def render():
    """Displays the resources page with categorized links."""
    st.title("📚 Course Resources")
    st.markdown("Find helpful links, documentation, and external materials related to the course.")

    # Define resource categories and their links
    # Using a more structured approach for easier management
    resource_categories = {
        "Python Fundamentals": [
            {"title": "Official Python Documentation (Python 3)", "url": "https://docs.python.org/3/"},
            {"title": "PEP 8 -- Style Guide for Python Code", "url": "https://peps.python.org/pep-0008/"},
            {"title": "Tutorialspoint: Python Tutorial", "url": "https://www.tutorialspoint.com/python/index.htm"},
            {"title": "Google's Python Class (for beginners)", "url": "https://developers.google.com/edu/python"},
            {"title": "Think Python 2e (Online Book)", "url": "http://greenteapress.com/thinkpython2/html/index.html"},
            {"title": "Complete Python 3 Bootcamp (GitHub Resources)", "url": "https://github.com/Pierian-Data/Complete-Python-3-Bootcamp"}
        ],
        "Development Tools & Environments": [
            {"title": "PyCharm IDE (Educational Access)", "url": "https://www.jetbrains.com/community/education/#students"},
            {"title": "PyCharm Official Tutorial: First Python Project", "url": "https://www.jetbrains.com/help/pycharm/creating-and-running-your-first-python-project.html"},
            {"title": "Tutorialspoint: PyCharm Tutorial", "url": "https://www.tutorialspoint.com/pycharm/index.htm"},
            {"title": "Google Colaboratory (Colab) - Welcome", "url": "https://colab.research.google.com/"},
            {"title": "Google Colab Tutorial Notebook (Example)", "url": "https://colab.research.google.com/github/ga642381/ML2021-Spring/blob/main/Colab/Google_Colab_Tutorial.ipynb"},
            {"title": "Tutorialspoint: Google Colab", "url": "https://www.tutorialspoint.com/google_colab/index.htm"}
        ],
        "Python Tutorials & Courses (General)": [
            {"title": "Data-Flair: Python Tutorial for Beginners", "url": "https://data-flair.training/blogs/python-tutorial/"},
            {"title": "Learn Python Programming (YouTube Channel - Programming with Mosh)", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"}, # Placeholder for actual YouTube link if known
            {"title": "Awesome Generative AI: Coding Assistants", "url": "https://github.com/steven2358/awesome-generative-ai?tab=readme-ov-file#coding"}
        ],
        "Natural Language Processing (NLP)": [
            {"title": "NLTK (Natural Language Toolkit) Documentation", "url": "https://www.nltk.org/"},
            {"title": "Speech and Language Processing (Jurafsky & Martin - Online Book)", "url": "https://web.stanford.edu/~jurafsky/slp3/"},
            {"title": "NLP is Fun! (Medium Article)", "url": "https://medium.com/@ageitgey/natural-language-processing-is-fun-9a0bff37854e"},
            {"title": "The Definitive Guide to Natural Language Processing (MonkeyLearn Blog)", "url": "https://monkeylearn.com/blog/definitive-guide-natural-language-processing/"},
            {"title": "Quora: How do I start with Natural Language Processing?", "url": "https://www.quora.com/How-do-I-start-with-Natural-Language-Processing"},
            {"title": "Ask HN: What are the best tools for text analysis in Python?", "url": "https://news.ycombinator.com/item?id=9733883"}
        ],
        "NLP Applications & Demos (Colab Notebooks)": [
            {"title": "Demo: Basic NLP Operations", "url": "https://colab.research.google.com/drive/1JZnBoyjHy8QYgKEbZCGR9J0-P0qQycC0?usp=sharing"},
            {"title": "Demo: Word Embedding Comparison", "url": "https://colab.research.google.com/drive/1t2EC7Aunf1qcsY4a50L4TFTXOM9SQB33?usp=sharing"},
            {"title": "In-Class Exercise 5: NLP Tasks", "url": "https://colab.research.google.com/drive/17v-A-3qFlYYoHypoux7o2PvZ_e2RFsln?usp=sharing"}
        ],
        "Sentiment Analysis": [
            {"title": "In-Depth Series: Sentiment Analysis with Transformers (Kaggle)", "url": "https://www.kaggle.com/code/emirkocak/in-depth-series-sentiment-analysis-w-transformers"},
            {"title": "Building a Sentiment Analysis App with ChatGPT and Druid (Imply Blog)", "url": "https://imply.io/blog/how-to-build-a-sentiment-analysis-application-with-chatgpt-and-druid"},
        ],
        "AI & Machine Learning (General)": [
            {"title": "Quora: AI vs Machine Learning vs NLP vs Deep Learning", "url": "https://www.quora.com/What-is-the-difference-between-AI-Machine-Learning-NLP-and-Deep-Learning"},
            {"title": "Google's Machine Learning Crash Course (Prerequisites & Prework)", "url": "https://developers.google.com/machine-learning/crash-course/prereqs-and-prework"},
            {"title": "Experiments with Google: AI Collection", "url": "https://experiments.withgoogle.com/collection/ai"}
        ],
        "Word Embeddings & Language Models": [
            {"title": "What Are Word Embeddings for Text? (Machine Learning Mastery)", "url": "https://machinelearningmastery.com/what-are-word-embeddings/"},
            {"title": "The Illustrated BERT, ELMo, and co. (Jay Alammar's Blog)", "url": "https://jalammar.github.io/illustrated-bert/"},
            {"title": "ULMFiT Overview (Humboldt-WI Blog)", "url": "https://humboldt-wi.github.io/blog/research/information_systems_1819/group4_ulmfit/"},
            {"title": "A Review of BERT-based Models (Towards Data Science)", "url": "https://towardsdatascience.com/a-review-of-bert-based-models-4ffdc0f15d58"},
            {"title": "Challenges in Reproducing GPT-3 (Jingfeng Yang's Blog)", "url": "https://jingfengyang.github.io/gpt/"}
        ],
        "Text Mining & Topic Modeling": [
            {"title": "Where to start with text mining (Ted Underwood's Blog)", "url": "https://tedunderwood.com/2012/08/14/where-to-start-with-text-mining/"},
            {"title": "BERTopic (GitHub - MaartenGr)", "url": "https://github.com/MaartenGr/BERTopic"},
            {"title": "Topic Modeling with Gensim (Python) - Machine Learning Plus", "url": "https://www.machinelearningplus.com/nlp/topic-modeling-gensim-python/"}
        ],
        "Web Scraping & Automation": [
            {"title": "Twitter API v2 Quick Start Guide", "url": "https://developer.x.com/en/docs/tutorials/step-by-step-guide-to-making-your-first-request-to-the-twitter-api-v2"},
            {"title": "Web Scraping 101 with Python (Greg Reda's Blog)", "url": "https://gregreda.com/2013/03/03/web-scraping-101-with-python/"},
            {"title": "Build a Python Web Crawler with ChatGPT (YouTube)", "url": "https://www.youtube.com/watch?v=B89Cf4pLNds"}, # Placeholder
            {"title": "GPT-4 Vision + Puppeteer for Web Automation (YouTube)", "url": "https://www.youtube.com/watch?v=VeQR17k7fiU"} # Placeholder
        ],
        "MLOps & Deployment": [
            {"title": "From Model-centric to Data-centric AI (Andrew Ng - YouTube)", "url": "https://www.youtube.com/watch?v=06-AZXmwHjo"} # Placeholder
        ],
        "Transformers & Conference Recordings (UNT Zoom)": [
            {"title": "Transformers - Session 1 (Recording)", "url": "https://unt.zoom.us/rec/share/L8-Zo_aX6QVsiOCcgZ84uNJRTNwybrNFv_WPZlZQWQr5d4NuQrBW5clscSxUbLtB.ryHtoLFwndhO6591"},
            {"title": "Transformers - Session 2 (Recording)", "url": "https://unt.zoom.us/rec/share/GSTRUEL4xvoqJg-2_oS-7LmIhKl5jESNswaLbBaN84h7S59lcmGIUgmpQV9oa4WH.94JD-V1s9iGMjmuw"}
        ],
        "LangChain & LLM Utilities": [
            {"title": "What is LangChain and How to Use It? (Product Hunt Stories)", "url": "https://www.producthunt.com/stories/what-is-langchain-how-to-use"},
            {"title": "LangChain Documentation: Web Scraping Use Case", "url": "https://python.langchain.com/docs/use_cases/web_scraping"},
            {"title": "KeyBERT: Keyword Extraction with BERT (MaartenGr)", "url": "https://maartengr.github.io/KeyBERT/"}
        ],
        "Neural Networks & GPT Projects": [
            {"title": "nanogpt Lecture (Andrej Karpathy - GitHub)", "url": "https://github.com/karpathy/ng-video-lecture"},
            {"title": "Neural Networks: Zero to Hero (Andrej Karpathy)", "url": "https://karpathy.ai/zero-to-hero.html"},
            {"title": "picoGPT Repository (Jay Mody - GitHub)", "url": "https://github.com/jaymody/picoGPT"}
        ],
        "Generative AI Practices": [
            {"title": "Generative AI Best Practices (GitHub Pages)", "url": "https://runawayhorse001.github.io/GenAI_Best_Practices/html/index.html"},
            {"title": "ArXiv Preprint: Generative AI (Example)", "url": "https://arxiv.org/abs/2301.09223"} # Example, replace with actual relevant paper
        ],
        "Python for Social Sciences": [
            {"title": "Python Tutorials for Social Scientists (Neal Caren)", "url": "https://nealcaren.github.io/python-tutorials/"}
        ]
    }

    # Display resources using expanders for each category
    for category, links in resource_categories.items():
        with st.expander(f"📂 {category}", expanded=False):
            for link_info in links:
                # Ensure URL is a string and not None before creating markdown
                if link_info.get("url") and isinstance(link_info.get("url"), str):
                    st.markdown(f"- [{link_info['title']}]({link_info['url']})", unsafe_allow_html=True)
                else:
                    st.markdown(f"- {link_info['title']} (URL not available)")
    
    st.markdown("---")
    st.info("Note: External links are provided for informational purposes. Content on external sites is not controlled by this platform.")
    
    render_footer()
