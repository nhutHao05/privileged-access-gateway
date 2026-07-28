from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Singleton scheduler — chỉ start/shutdown qua lifespan trong main.py
scheduler = AsyncIOScheduler()
