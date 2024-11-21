"""
this is an example of the client code written by fastapi that will interact with the server
"""
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.post("/callback/{client_task_id}")
async def callback(client_task_id: int, data: dict):
    print(f'callback client task id: {client_task_id}, data: {data}')


if __name__ == "__main__":
    uvicorn.run("client_example:app", host="0.0.0.0", port=9000)