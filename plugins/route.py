from aiohttp import web

routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("Madflix_Bots")




# Jishu Developer 
# Don't Remove Credit 🥺
# Telegram Channel @Forever_TN
# Backup Channel @AniKinolar_Kanal
# Developer @Yegerist_mvp
