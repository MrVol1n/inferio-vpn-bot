from datetime import datetime, timezone
import httpx
from app.config import settings
class RemnawaveError(RuntimeError): pass
class RemnawaveClient:
    def __init__(self): self.base=settings.remnawave_base_url.rstrip('/'); self.prefix=settings.remnawave_api_prefix.rstrip('/')
    def headers(self): return {'Authorization':f'Bearer {settings.remnawave_token}','Content-Type':'application/json'}
    async def req(self, method, path, **kwargs):
        if not self.base or not settings.remnawave_token: raise RemnawaveError('Remnawave is not configured')
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.request(method,f'{self.base}{self.prefix}{path}',headers=self.headers(),**kwargs)
            if r.status_code>=400: raise RemnawaveError(f'{r.status_code}: {r.text[:1000]}')
            return r.json() if r.content else {}
    @staticmethod
    def unwrap(x): return x.get('response',x) if isinstance(x,dict) else x
    async def find_user_by_telegram_id(self, telegram_id): return self.unwrap(await self.req('GET',f'/users/by-telegram-id/{telegram_id}'))
    async def create_user(self, username, expire_at, telegram_id, squads, device_limit=0, traffic_limit_gb=0):
        body={'username':username,'expireAt':expire_at.astimezone(timezone.utc).isoformat(),'telegramId':telegram_id,'activeInternalSquads':squads,'hwidDeviceLimit':device_limit or 0,'trafficLimitBytes':traffic_limit_gb*1024**3,'status':'ACTIVE','tag':'inferio'}
        return self.unwrap(await self.req('POST','/users',json=body))
    async def update_user(self, uuid, expire_at=None, squads=None, device_limit=None, traffic_limit_gb=None):
        body={'uuid':uuid}
        if expire_at is not None: body['expireAt']=expire_at.astimezone(timezone.utc).isoformat()
        if squads is not None: body['activeInternalSquads']=squads
        if device_limit is not None: body['hwidDeviceLimit']=device_limit
        if traffic_limit_gb is not None: body['trafficLimitBytes']=traffic_limit_gb*1024**3
        return self.unwrap(await self.req('PATCH','/users',json=body))
    async def enable(self, uuid): return self.unwrap(await self.req('POST',f'/users/{uuid}/actions/enable'))
    async def disable(self, uuid): return self.unwrap(await self.req('POST',f'/users/{uuid}/actions/disable'))
    async def revoke(self, uuid): return self.unwrap(await self.req('POST',f'/users/{uuid}/actions/revoke'))
    async def list_nodes(self):
        x=self.unwrap(await self.req('GET','/nodes')); return x.get('nodes',x) if isinstance(x,dict) else x
    async def list_squads(self):
        x=self.unwrap(await self.req('GET','/internal-squads')); return x.get('internalSquads',x) if isinstance(x,dict) else x
    async def get_subscription_by_uuid(self, uuid):
        return self.unwrap(await self.req('GET',f'/subscriptions/by-uuid/{uuid}'))
