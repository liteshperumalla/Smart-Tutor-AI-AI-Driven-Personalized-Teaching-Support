"""Static content for the home dashboard widgets."""

ANNOUNCEMENTS = [
    {
        "id": "welcome",
        "title": "Welcome!",
        "body": "Welcome to Smart AI Tutor! Your personalized learning assistant is ready to help you succeed.",
        "accent": "#3b82f6",
    },
    {
        "id": "getting-started",
        "title": "Getting Started",
        "body": "Explore the features: ask questions, generate quizzes, and access course materials.",
        "accent": "#10b981",
    },
]

PROFESSOR = {
    "name": "Dr. Haihua Chen",
    "links": [
        {"label": "LinkedIn", "url": "https://www.linkedin.com/in/haihua-chen/"},
        {
            "label": "Scholar",
            "url": "https://scholar.google.com/citations?user=URmnWAQAAAAJ",
        },
    ],
    "email": "haihua.chen@unt.edu",
}

COURSE_TOPICS = [
    {
        "title": "Introduction to Python",
        "url": "https://unt.instructure.com/courses/117821/pages/week-1-lecture-materials?module_item_id=7518917",
    },
    {
        "title": "Python Basics 1",
        "url": "https://unt.instructure.com/courses/117821/pages/week-2-lecture-materials?module_item_id=7518922",
    },
    {
        "title": "Python Basics 2",
        "url": "https://unt.instructure.com/courses/117821/pages/week-3-lecture-materials?module_item_id=7518928",
    },
    {
        "title": "Web Scraping using Python",
        "url": "https://unt.instructure.com/courses/117821/pages/week-4-lecture-materials?module_item_id=7518935",
    },
    {
        "title": "Data Cleaning and Data Quality",
        "url": "https://unt.instructure.com/courses/117821/pages/week-5-lecture-materials?module_item_id=7518942",
    },
    {
        "title": "Feature Extraction",
        "url": "https://unt.instructure.com/courses/117821/pages/week-6-lecture-materials?module_item_id=7518949",
    },
    {
        "title": "Word Embedding and Transformer",
        "url": "https://unt.instructure.com/courses/117821/pages/week-7-lecture-materials?module_item_id=7815101",
    },
    {
        "title": "Topic Modeling",
        "url": "https://unt.instructure.com/courses/117821/pages/week-10-lecture-materials-2?module_item_id=7518962",
    },
    {
        "title": "Sentiment Analysis",
        "url": "https://unt.instructure.com/courses/117821/pages/week-12-lecture-materials?module_item_id=7518972",
    },
    {
        "title": "Text Classification",
        "url": "https://unt.instructure.com/courses/117821/pages/week-13-lecture-materials?module_item_id=7518976",
    },
    {
        "title": "Generative AI in NLP",
        "url": "https://unt.instructure.com/courses/117821/pages/week-14-lecture-materials?module_item_id=7518981",
    },
]

QUICK_ACTIONS = [
    {
        "title": "Start chatting",
        "description": "Ask course-aware questions with citations.",
        "href": "/chat",
    },
    {
        "title": "Generate a quiz",
        "description": "Create targeted quizzes with instant scoring.",
        "href": "/quiz",
    },
    {
        "title": "Code sandbox",
        "description": "Write and execute code in multiple languages.",
        "href": "/code",
    },
    {
        "title": "Research mode",
        "description": "Upload sources and preview citations.",
        "href": "/research",
    },
]
