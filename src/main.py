import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api import router
from comfy import ComfyServer, comfy_servers, logger
from config import SERVICE_PORT
from database import init_rdb

init_rdb()


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    for comfy_server in comfy_servers:
        task = asyncio.create_task(comfy_server.listen())
        tasks.append(task)

    yield

    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f'task {task.get_name()} cancelled')

app = FastAPI(lifespan=lifespan)

@app.post('/callback/{id}')
async def callback(id: int, data: dict):
    print(f'callback id: {id}, data: {data}')

app.include_router(router)

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=int(SERVICE_PORT))