from aiogram import Dispatcher
from app.bot.handlers import start,common,shop,marketing,admin

def build_dispatcher():
    dp=Dispatcher();dp.include_router(start.router);dp.include_router(shop.router);dp.include_router(marketing.router);dp.include_router(common.router);dp.include_router(admin.router);return dp
