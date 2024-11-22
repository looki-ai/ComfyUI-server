import asyncio
import json
import logging
import os
import uuid

import aiofiles
import httpx
import websockets

from config import CALLBACK_BASE_URL, COMFYUI_ENDPOINTS, DEFAULT_FAILED_IMAGE_PATH
from database import ComfyUIRecord
from database.repository import RecordRepository
from s3 import upload_image_to_s3
from workflows.clean_local_file import CLEAN_LOCAL_FILE_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class ComfyUIServer:
    def __init__(self, endpoint: str):
        self.async_http_client = httpx.AsyncClient(timeout=30.0)
        self.queue_remaining = 0
        self.endpoint = endpoint
        self.client_id = uuid.uuid4().hex
        self.callback_base_url = CALLBACK_BASE_URL
        self.default_failed_image_path = DEFAULT_FAILED_IMAGE_PATH

    async def queue_prompt(self, client_task_id: int, prompt: dict) -> ComfyUIRecord:
        """commit a prompt to the comfyui server"""
        uri = f"http://{self.endpoint}/prompt"
        payload = {"prompt": prompt, "client_id": self.client_id}
        response = await self.async_http_client.post(uri, json=payload)
        logger.debug(f"queue prompt response: {response.text}")
        comfyui_task_id = response.json()["prompt_id"]
        comfyui_record = ComfyUIRecord(client_task_id=client_task_id, comfyui_task_id=comfyui_task_id)
        comfyui_record = await RecordRepository.create(comfyui_record)
        return comfyui_record

    async def listen(self):
        """listen messages from the comfyui server"""
        uri = f"ws://{self.endpoint}/ws?clientId={self.client_id}"
        async with websockets.connect(uri) as websocket:
            logger.info("connected to comfyui server")
            while True:
                try:
                    message = await websocket.recv()
                    json_data = json.loads(message)
                    if json_data.get("type") == "executing" and json_data.get("data", {}).get("node") is None:
                        # comfyui server has finished the prompt task
                        try:
                            comfyui_task_id = json_data["data"]["prompt_id"]
                            image = await self._retrieve_image(comfyui_task_id)
                            comfyui_record = await RecordRepository.retrieve_by_comfyui_task_id(comfyui_task_id)
                            s3_resp = await upload_image_to_s3(image)
                            logger.info(f"uploaded image to s3: {s3_resp}")
                            if not s3_resp["success"]:
                                logger.error(f"upload image to s3 error: {s3_resp}")
                                await self.store_failed_image(comfyui_record, image)
                                continue

                            comfyui_record.s3_key = s3_resp["key"]
                            comfyui_record = await RecordRepository.update(comfyui_record)
                            await self.client_callback(comfyui_record)
                        except Exception as e:
                            logger.error(f"webhook or s3 error: {e}")
                            await self.store_failed_image(comfyui_record, image)
                        finally:
                            await self.clean_local_file(is_input=False, image_path=comfyui_record.comfyui_filepath)

                    elif json_data["type"] == "status":
                        # update queue remaining num
                        self.queue_remaining = json_data["data"]["status"]["exec_info"]["queue_remaining"]
                        logger.info(f"server {self.client_id} remaining: {self.queue_remaining}")

                except websockets.exceptions.ConnectionClosed:
                    logger.warning("connection closed, reconnecting...")
                    await asyncio.sleep(5)
                    await self.listen()
                except Exception as e:
                    logger.error(f"server {self.client_id} websocket error: {e}")

    async def _retrieve_image(self, comfyui_task_id: str) -> bytes:
        """retrieve prompt task result(image) from comfyui"""
        # 1. get the image path from the comfyui server
        history_uri = f"http://{self.endpoint}/history/{comfyui_task_id}"
        response = await self.async_http_client.get(history_uri)
        history = response.json()
        output_info = history[comfyui_task_id]["outputs"]
        for key in output_info:
            if "images" not in output_info[key]:
                continue
            image_info = output_info[key]["images"][0]  # note now only retrieve the first image
            image_path = image_info["filename"]
            if image_info["subfolder"]:
                image_path = f"{image_info['subfolder']}/{image_path}"

            comfyui_record = await RecordRepository.retrieve_by_comfyui_task_id(comfyui_task_id)
            comfyui_record.comfyui_filepath = image_path
            await RecordRepository.update(comfyui_record)

            # 2. retrieve the image from the comfyui server
            view_uri = f"http://{self.endpoint}/view"
            params = {"filename": image_path}
            response = await self.async_http_client.get(view_uri, params=params)
            return response.content

    async def client_callback(self, comfyui_record: ComfyUIRecord):
        """callback to the client server"""
        uri = f"{self.callback_base_url}/{comfyui_record.client_task_id}"
        response = await self.async_http_client.post(uri, json=comfyui_record.to_dict())
        logger.debug(f"callback response: {response.text}")
        return response.json()

    async def clean_local_file(self, is_input: bool, image_path: str):
        """clean input or output file from the comfyui server"""
        prompt = CLEAN_LOCAL_FILE_PROMPT_TEMPLATE.substitute(type="input" if is_input else "output", path=image_path)
        prompt_json = json.loads(prompt)
        uri = f"http://{self.endpoint}/prompt"
        payload = {
            "prompt": prompt_json,
            # NOTE ignore client_id for now, in case of tracking the clean file system message
        }
        response = await self.async_http_client.post(uri, json=payload)
        logger.debug(f"clean file response: {response.text}")

    async def upload_image(self, image: bytes):
        """upload image to the comfyui server"""
        file_name = f"{uuid.uuid4()}.png"
        uri = f"http://{self.endpoint}/upload/image"
        response = await self.async_http_client.post(uri, files={"image": (file_name, image, "image/png")})
        logger.debug(f"upload image response: {response.text}")
        return response.json()

    async def store_failed_image(self, record: ComfyUIRecord, image: bytes):
        """Store failure prompt result in the fallback path."""
        file_path = os.path.join(self.default_failed_image_path, record.comfyui_filepath)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(image)


comfyui_servers = [ComfyUIServer(endpoint) for endpoint in COMFYUI_ENDPOINTS]
