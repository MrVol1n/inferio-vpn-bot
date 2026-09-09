from decimal import Decimal
import httpx
from app.config import settings
class PlategaError(RuntimeError): pass
class PlategaClient:
    def __init__(self): self.base=settings.platega_api_base.rstrip('/')
    def headers(self): return {'X-MerchantId':settings.platega_merchant_id,'X-Secret':settings.platega_secret,'Content-Type':'application/json'}
    async def create_payment(self, amount:Decimal, description:str, payload:str, username:str|None, telegram_id:int):
        body={'paymentDetails':{'amount':float(amount),'currency':'RUB'},'description':description,'return':settings.platega_return_url,'failedUrl':settings.platega_return_url,'payload':payload,'metadata':{'userId':str(telegram_id),'userName':username or ''}}
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(f'{self.base}/v2/transaction/process',headers=self.headers(),json=body)
            if r.status_code>=400: raise PlategaError(f'{r.status_code}: {r.text[:500]}')
            return r.json()
    async def get_transaction(self, transaction_id:str):
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(f'{self.base}/transaction/{transaction_id}',headers=self.headers())
            r.raise_for_status(); return r.json()
