import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api import router
from comfy import ComfyClient
from database import init_rdb

init_rdb()


@asynccontextmanager
async def lifespan(app: FastAPI):
    comfy_client = ComfyClient.get_instance()
    task = asyncio.create_task(comfy_client.listen())
    try:
        yield
    finally:
        task.cancel()

app = FastAPI(lifespan=lifespan)

@app.post('/callback/{id}')
async def callback(id: int, data: dict):
    print(f'callback id: {id}, data: {data}')

app.include_router(router)

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000)