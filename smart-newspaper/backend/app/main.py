"""FastAPI entrypoint for Smart Personnel Newspaper backend."""

from __future__ import annotations

from fastapi import FastAPI

from app.core.logging_config import setup_logging
from app.routers import adaptive_ranking, admin, ai_classification, advanced_search, analytics, articles, articles_filter, auth, bookmarks, citations, classification, content_moderation, crawl, events, health, keywords, moderation, monitoring, multilabel, reports, newspaper_citations, newspaper_editions, newspaper_layout, personal_feed, print_router, recommendations, prioritization, search, topics, tracking, trending

setup_logging()

app = FastAPI(title="Smart Personnel Newspaper Backend")
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(ai_classification.router)
app.include_router(crawl.router)
app.include_router(events.router)
app.include_router(bookmarks.router)
app.include_router(articles_filter.router)
app.include_router(articles.router)
app.include_router(citations.router)
app.include_router(classification.router)
app.include_router(multilabel.router)
app.include_router(keywords.router)
app.include_router(content_moderation.router)
app.include_router(moderation.router)
app.include_router(personal_feed.router)
app.include_router(recommendations.router)
app.include_router(topics.router)
app.include_router(analytics.router)
app.include_router(adaptive_ranking.router)
app.include_router(admin.router)
app.include_router(monitoring.router)
app.include_router(reports.router)
app.include_router(print_router.router)
app.include_router(prioritization.router)
app.include_router(newspaper_layout.router)
app.include_router(newspaper_citations.router)
app.include_router(newspaper_editions.router)

app.include_router(search.router)
app.include_router(advanced_search.router)
app.include_router(trending.router)
app.include_router(tracking.router)
