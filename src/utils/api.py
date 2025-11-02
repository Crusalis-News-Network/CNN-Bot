#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Updated FastAPI routes with reverse index integration
#
from contextlib import asynccontextmanager

from fastapi import APIRouter, Query, HTTPException, FastAPI
from typing import Optional
from .db import NewsSchema, Category
from fastapi.responses import FileResponse, HTMLResponse
from .globals import bot, logger

from .idx import (
    initialize_idx,
    search_news,
    news_index
)


router = APIRouter(prefix="", tags=["News"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await initialize_idx(NewsSchema)
        logger.info("Search index initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize search index: {e}")

app = FastAPI(lifespan=lifespan)


@router.get("/api/news/{title}")
async def get_news_by_title(title: str, q: Optional[str] = None):
    try:
        candidate_ids = await search_news(title, limit=20)
        
        if candidate_ids:
            news_items = await NewsSchema.filter(id__in=candidate_ids).all()
            id_to_item = {item.id: item for item in news_items}
            ordered_items = [id_to_item[news_id] for news_id in candidate_ids if news_id in id_to_item]
        else:
            ordered_items = await NewsSchema.search_query(topic=title)
        
        return {
            "news": [await item.to_dict(bot) for item in ordered_items], 
        }
    except Exception as e:
        logger.error(f"Error in get_news_by_title: {e}")
        news_items = await NewsSchema.search_query(topic=title)
        return {"news": [await item.to_dict(bot) for item in news_items], "q": q}

@router.get('/api/news/search/all/{query}')
async def search_all_news(query: str, limit: int = 10):
    try:
        if news_index.is_initialized:
            candidate_ids = await search_news(query, limit=limit)
            
            if candidate_ids:
                news_items = await NewsSchema.filter(id__in=candidate_ids).all()
                
                id_to_item = {item.id: item for item in news_items}
                ordered_items = [id_to_item[news_id] for news_id in candidate_ids if news_id in id_to_item]
                
                return [await item.to_dict(bot) for item in ordered_items]
        
        news_items = await NewsSchema.search_all(query.upper(), limit)
        if len(news_items) == 0:
            return {"error": 404}
        return [await item.to_dict(bot) for item in news_items]
        
    except Exception as e:
        logger.error(f"Error in search_all_news: {e}")
        news_items = await NewsSchema.search_all(query.upper(), limit)
        return [await item.to_dict(bot) for item in news_items]

@router.get("/api/recent")
async def get_recent():
    news_items = await NewsSchema.get_recent(10)
    return [await item.to_dict(bot) for item in news_items]


@router.get("/api/categories")
async def categories():
    l = []
    for key in Category:
        l.append(key.value)
    return {"categories": l}


app.include_router(router)