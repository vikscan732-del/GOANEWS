import os
import json
import time
import feedparser
from google import genai

# =========================================================
# 1. FETCH GOA NEWS FROM RSS FEEDS
# =========================================================

FEEDS = [
    "https://news.google.com/rss/search?q=Goa+news&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Goa+sports+OR+Goa+football+OR+Goa+cricket&hl=en-IN&gl=IN&ceid=IN:en",
    "https://digitalgoa.com/feed/"
]

raw_articles = []
seen_titles = set()

for url in FEEDS:

    print("Fetching:", url)

    try:
        feed = feedparser.parse(url)

        for entry in feed.entries:

            title = entry.get("title", "").strip()

            if not title:
                continue

            title_key = title.lower()

            if title_key not in seen_titles:

                seen_titles.add(title_key)

                raw_articles.append({
                    "title": title,
                    "summary": entry.get("summary", "")
                })

    except Exception as e:

        print("Feed error:", e)


# Limit to 50 articles
raw_articles = raw_articles[:50]

print("Total articles found:", len(raw_articles))


# =========================================================
# 2. PREPARE TEXT FOR GEMINI
# =========================================================

news_input = []

for idx, entry in enumerate(raw_articles, 1):

    news_input.append(
        f"{idx}. Title: {entry['title']}\n"
        f"Context: {entry['summary']}"
    )

combined_text = "\n\n".join(news_input)


# =========================================================
# 3. GEMINI AI SUMMARIZATION
# =========================================================

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:

    raise RuntimeError(
        "GEMINI_API_KEY environment variable is missing."
    )

client = genai.Client(api_key=api_key)


prompt = f"""
You are an editor for a clean, mobile-first Goa news portal.

Rewrite and summarize every news story below in your own words.

Rules:

1. Keep each headline short and clear.
2. Write a 1-2 sentence summary.
3. Do not invent facts.
4. Do not add information that is not present in the source.
5. Assign exactly ONE category.

Allowed categories:

- Sports
- Politics
- Tourism
- Weather
- Crime
- Civic
- Entertainment
- Business
- General

Return ONLY a valid JSON array.

Each object MUST contain:

"category"
"headline"
"summary"

News:

{combined_text}
"""


# =========================================================
# 4. GEMINI MODEL RETRY
# =========================================================

candidate_models = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash"
]

response = None


for model_name in candidate_models:

    for attempt in range(2):

        try:

            print(
                f"Trying model: {model_name} "
                f"(Attempt {attempt + 1})..."
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "response_mime_type": "application/json"
                }
            )

            if response and response.text:

                print(
                    "Successfully generated using",
                    model_name
                )

                break

        except Exception as e:

            print(
                f"Failed with {model_name}: {e}"
            )

            time.sleep(3)

    if response:

        break


if not response:

    raise RuntimeError(
        "All Gemini models failed."
    )


# =========================================================
# 5. PARSE GEMINI JSON
# =========================================================

try:

    news_data = json.loads(response.text)

except Exception as e:

    print("Gemini returned invalid JSON.")

    print(response.text)

    raise RuntimeError(
        f"Could not parse Gemini response: {e}"
    )


if not isinstance(news_data, list):

    raise RuntimeError(
        "Gemini response is not a JSON array."
    )


# Keep maximum 50
news_data = news_data[:50]


print(
    "AI processed articles:",
    len(news_data)
)


# =========================================================
# 6. SVG CATEGORY ICONS
# =========================================================

SVG_ICONS = {

    "Sports":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<circle cx="12" cy="12" r="10"/>'
    '<path d="M12 2a14.5 14.5 0 0 0 0 20 '
    '14.5 14.5 0 0 0 0-20"/>'
    '<path d="M2 12h20"/></svg>',

    "Politics":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M4 22h16M2 10h20M12 2l8 6H4z '
    'M6 10v9M10 10v9M14 10v9M18 10v9"/>'
    '</svg>',

    "Tourism":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<circle cx="12" cy="12" r="4"/>'
    '<path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41 '
    'M17.66 17.66l1.41 1.41M2 12h2M20 12h2 '
    'M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>'
    '</svg>',

    "Weather":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79 '
    'a4.5 4.5 0 1 1 0 9Z"/>'
    '</svg>',

    "Crime":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7 '
    'c0 6 8 10 8 10z"/>'
    '</svg>',

    "Civic":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<rect width="16" height="20" x="4" y="2" rx="2" ry="2"/>'
    '<path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01 '
    'M12 10h.01M12 14h.01M16 10h.01M16 14h.01 '
    'M8 10h.01M8 14h.01"/>'
    '</svg>',

    "Entertainment":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<polygon points="6 3 20 12 6 21 6 3"/>'
    '</svg>',

    "Business":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>'
    '<polyline points="16 7 22 7 22 13"/>'
    '</svg>',

    "General":
    '<svg class="cat-icon" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<circle cx="12" cy="12" r="10"/>'
    '<line x1="12" y1="16" x2="12" y2="12"/>'
    '<line x1="12" y1="8" x2="12.01" y2="8"/>'
    '</svg>'
}


# =========================================================
# 7. CATEGORY FILTER BUTTONS
# =========================================================

categories = [
    "All",
    "Sports",
    "Politics",
    "Tourism",
    "Weather",
    "Crime",
    "Civic",
    "Entertainment",
    "Business"
]


category_pills_html = "".join([

    f'<button class="pill '
    f'{"active" if cat == "All" else ""}" '
    f'onclick="filterNews(\'{cat}\')">'
    f'{SVG_ICONS.get(cat, "")}'
    f'<span>{cat}</span>'
    f'</button>'

    for cat in categories
])


# =========================================================
# 8. CREATE WEBSITE NEWS CARDS
# =========================================================

articles_html = ""


for item in news_data:

    cat = str(
        item.get("category", "General")
    ).strip().capitalize()

    if cat not in SVG_ICONS:

        cat = "General"


    headline = str(
        item.get("headline", "")
    ).strip()


    summary = str(
        item.get("summary", "")
    ).strip()


    icon_svg = SVG_ICONS.get(
        cat,
        SVG_ICONS["General"]
    )


    articles_html += f"""
        <article
            class="card card-{cat.lower()}"
            data-category="{cat}"
        >

            <div class="card-header">

                <span class="tag tag-{cat.lower()}">

                    {icon_svg}

                    {cat}

                </span>

            </div>

            <h2 class="headline">
                {headline}
            </h2>

            <p class="summary">
                {summary}
            </p>

        </article>
    """


# =========================================================
# 9. CREATE WEBSITE HTML
# =========================================================

html_content = f"""<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width,
    initial-scale=1.0"
>

<title>Goa News Today – Top 50 Goa News | TVGoa</title>

<meta name="description" content="Latest Goa news today: Top 50 Goa news headlines covering politics, crime, tourism, sports, weather, business and civic updates.">
<meta name="keywords" content="Goa news today, Goa latest news, Goa news, Goa breaking news, Goa Top 50 news, Goa news headlines, news in Goa">
<link rel="canonical" href="https://tvgoa.online/goa-news-today.html">


<style>

:root {{

    --bg: #f8fafc;

    --card-bg: #ffffff;

    --text: #0f172a;

    --muted: #475569;

    --border: #e2e8f0;

    --shadow:
        0 2px 6px rgba(0,0,0,0.04);
}}


@media (prefers-color-scheme: dark) {{

    :root {{

        --bg: #0b0f19;

        --card-bg: #131b2e;

        --text: #f8fafc;

        --muted: #94a3b8;

        --border: #1e293b;

        --shadow:
            0 2px 8px rgba(0,0,0,0.3);
    }}
}}


* {{

    box-sizing: border-box;

    margin: 0;

    padding: 0;
}}


body {{

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Roboto,
        sans-serif;

    background-color: var(--bg);

    color: var(--text);

    line-height: 1.6;

    padding: 16px;

    max-width: 680px;

    margin: 0 auto;
}}


header {{

    border-bottom:
        2px solid var(--border);

    padding-bottom: 12px;

    margin-bottom: 16px;
}}


h1 {{

    font-size: 1.7rem;

    font-weight: 900;

    letter-spacing: -0.5px;

    color: var(--text);
}}


.subtitle {{

    font-size: 0.88rem;

    color: var(--muted);

    font-weight: 500;
}}


.filter-bar {{

    display: flex;

    gap: 8px;

    overflow-x: auto;

    padding-bottom: 12px;

    margin-bottom: 16px;

    -webkit-overflow-scrolling: touch;

    scrollbar-width: none;
}}


.filter-bar::-webkit-scrollbar {{

    display: none;
}}


.pill {{

    display: inline-flex;

    align-items: center;

    gap: 6px;

    background:
        var(--card-bg);

    color:
        var(--text);

    border:
        1px solid var(--border);

    padding:
        7px 14px;

    border-radius: 24px;

    font-size: 0.85rem;

    font-weight: 700;

    cursor: pointer;

    white-space: nowrap;

    box-shadow:
        var(--shadow);

    transition:
        all 0.2s ease;
}}


.pill.active {{

    background: #2563eb;

    color: #ffffff;

    border-color: #2563eb;
}}


.pill .cat-icon {{

    width: 14px;

    height: 14px;
}}


.card {{

    background:
        var(--card-bg);

    border-radius: 12px;

    padding:
        16px 18px;

    margin-bottom: 14px;

    border:
        1px solid var(--border);

    border-left:
        5px solid #94a3b8;

    box-shadow:
        var(--shadow);

    transition:
        transform 0.15s ease;
}}


.card:hover {{

    transform:
        translateY(-2px);
}}


.card.hidden {{

    display: none;
}}


.card-sports {{
    border-left-color: #10b981;
}}

.card-politics {{
    border-left-color: #ef4444;
}}

.card-tourism {{
    border-left-color: #0ea5e9;
}}

.card-weather {{
    border-left-color: #f59e0b;
}}

.card-crime {{
    border-left-color: #8b5cf6;
}}

.card-entertainment {{
    border-left-color: #ec4899;
}}

.card-business {{
    border-left-color: #f97316;
}}

.card-civic {{
    border-left-color: #64748b;
}}


.card-header {{

    margin-bottom: 8px;
}}


.tag {{

    display: inline-flex;

    align-items: center;

    gap: 5px;

    font-size: 0.72rem;

    font-weight: 800;

    padding:
        4px 9px;

    border-radius: 6px;

    text-transform:
        uppercase;

    letter-spacing:
        0.5px;
}}


.tag .cat-icon {{

    width: 12px;

    height: 12px;
}}


.tag-sports {{
    background: #dcfce7;
    color: #166534;
}}

.tag-politics {{
    background: #fee2e2;
    color: #991b1b;
}}

.tag-tourism {{
    background: #e0f2fe;
    color: #075985;
}}

.tag-weather {{
    background: #fef3c7;
    color: #92400e;
}}

.tag-crime {{
    background: #f3e8ff;
    color: #5b21b6;
}}

.tag-entertainment {{
    background: #fce7f3;
    color: #9d174d;
}}

.tag-business {{
    background: #ffedd5;
    color: #9a3412;
}}

.tag-civic {{
    background: #f1f5f9;
    color: #334155;
}}


.headline {{

    font-size: 1.12rem;

    font-weight: 800;

    line-height: 1.4;

    margin-bottom: 8px;

    color:
        var(--text);
}}


.summary {{

    font-size: 0.94rem;

    color:
        var(--muted);

    line-height: 1.55;
}}

</style>

</head>


<body>


<header>

<h1>Goa News Today – Top 50</h1>

<p class="subtitle">
Latest Goa News Headlines · Updated Daily
</p>

</header>


<div class="filter-bar">

{category_pills_html}

</div>


<main id="news-container">

{articles_html}

</main>


<script>

function filterNews(selectedCategory) {{

    const buttons =
        document.querySelectorAll('.pill');


    buttons.forEach(btn => {{

        const span =
            btn.querySelector('span');

        const btnText =
            span
            ? span.innerText
            : btn.innerText;


        if (
            btnText.trim().toLowerCase()
            ===
            selectedCategory.toLowerCase()
        ) {{

            btn.classList.add('active');

        }} else {{

            btn.classList.remove('active');

        }}

    }});


    const items =
        document.querySelectorAll('.card');


    items.forEach(item => {{

        const itemCat =
            item.getAttribute(
                'data-category'
            );


        if (
            selectedCategory === 'All'
            ||
            itemCat.toLowerCase()
            ===
            selectedCategory.toLowerCase()
        ) {{

            item.classList.remove('hidden');

        }} else {{

            item.classList.add('hidden');

        }}

    }});

}}

</script>


</body>

</html>
"""


# =========================================================
# 10. SAVE WEBSITE
# =========================================================

with open(
    "goa-news-today.html",
    "w",
    encoding="utf-8"
) as f:

    f.write(html_content)


print("goa-news-today.html created successfully.")


# =========================================================
# 11. CREATE NEWS.JSON FOR ANDROID APP
# =========================================================

android_news = []


for index, item in enumerate(
    news_data[:50],
    1
):

    android_news.append({

        "rank": index,

        "category":
            str(
                item.get(
                    "category",
                    "General"
                )
            ).strip(),

        "headline":
            str(
                item.get(
                    "headline",
                    ""
                )
            ).strip(),

        "summary":
            str(
                item.get(
                    "summary",
                    ""
                )
            ).strip()

    })


# =========================================================
# 12. SAVE JSON
# =========================================================

with open(
    "news.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        android_news,
        f,
        ensure_ascii=False,
        indent=2
    )


print(
    "news.json created successfully."
)

print(
    "Articles in news.json:",
    len(android_news)
)


# =========================================================
# 13. FINAL STATUS
# =========================================================

print("")
print("========================================")
print("GOA NEWS UPDATE COMPLETE")
print("========================================")
print("Website : goa-news-today.html")
print("Android : news.json")
print("Articles:", len(android_news))


print("========================================")


# =========================================================
# CREATE NEWS.JSON FOR ANDROID APP
# =========================================================

android_news = []

for index, item in enumerate(news_data[:50], 1):

    android_news.append({
        "rank": index,
        "category": str(
            item.get("category", "General")
        ).strip(),
        "headline": str(
            item.get("headline", "")
        ).strip(),
        "summary": str(
            item.get("summary", "")
        ).strip()
    })


with open(
    "news.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        android_news,
        f,
        ensure_ascii=False,
        indent=2
    )


print("================================")
print("GOA NEWS UPDATE COMPLETE")
print("================================")
print("goa-news-today.html created")
print("news.json created")
print("Articles:", len(android_news))
