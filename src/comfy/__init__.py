import asyncio
import json
import logging
import os
import uuid

import aiofiles
import httpx
import websockets

from config import (
    CALL_BACK_BASE_URL,
    FALLBACK_PATH,
    COMFY_ENDPOINTS
)
from database import Record
from database.repository import RecordRepository
from s3 import upload_image_to_s3
from workflows.clean_file import CLEAN_FILE_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class ComfyServer:
    def __init__(self, endpoint: str):
        self.queue_remaining = 0
        self.endpoint = endpoint
        self.client_id = uuid.uuid4().hex
        self.callback_base_url = CALL_BACK_BASE_URL
        self.fallback_path = FALLBACK_PATH

    async def queue_prompt(self, client_task_id: int, prompt: dict) -> Record:
        """commit a prompt to the comfy server"""
        uri = f'http://{self.endpoint}/prompt'
        payload = {
            'prompt': prompt,
            'client_id': self.client_id
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(uri, json=payload)
            logger.debug(f'queue prompt response: {response.text}')
            comfy_task_id = response.json()['prompt_id']
            record = Record(client_task_id=client_task_id, comfy_task_id=comfy_task_id)
            record = await RecordRepository.create(record)
            return record

    async def listen(self):
        """listen messages from the comfy server"""
        uri = f'ws://{self.endpoint}/ws?clientId={self.client_id}'
        async with websockets.connect(uri) as websocket:
            logger.info('connected to comfy server')
            while True:
                try:
                    message = await websocket.recv()
                    json_data = json.loads(message)
                    if json_data.get("type") == "executing" and json_data.get("data", {}).get("node") is None:
                        # comfy server has finished the prompt task
                        try:
                            comfy_task_id = json_data['data']['prompt_id']
                            image = await self._retrieve_image(comfy_task_id)
                            record = await RecordRepository.retrieve_by_comfy_task_id(comfy_task_id)
                            s3_resp = await upload_image_to_s3(image)
                            logger.info(f'uploaded image to s3: {s3_resp}')
                            if not s3_resp['success']:
                                logger.error(f'upload image to s3 error: {s3_resp}')
                                await self.store_failure(record, image)
                                continue

                            record.s3_key = s3_resp['key']
                            record = await RecordRepository.update(record)
                            await self.hook(record)
                        except Exception as e:
                            logger.error(f'webhook or s3 error: {e}')
                            await self.store_failure(record, image)
                        finally:
                            await self.clean_file(is_input=False, image_path=record.comfy_filepath)

                    elif json_data['type'] == 'status':
                        # update queue remaining num
                        self.queue_remaining = json_data['data']['status']['exec_info']['queue_remaining']
                        logger.info(f'server {self.client_id} remaining: {self.queue_remaining}')

                except websockets.exceptions.ConnectionClosed:
                    logger.warning('connection closed, reconnecting...')
                    await asyncio.sleep(5)
                    await self.listen()
                except Exception as e:
                    logger.error(f'server {self.client_id} websocket error: {e}')

    async def _retrieve_image(self, comfy_task_id: str) -> bytes:
        """retrieve prompt task result(image) from comfyui"""
        # 1. get the image path from the comfy server
        history_uri = f'http://{self.endpoint}/history/{comfy_task_id}'
        async with httpx.AsyncClient() as client:
            response = await client.get(history_uri)
            history = response.json()
        output_info = history[comfy_task_id]['outputs']
        for key in output_info:
            if 'images' not in output_info[key]:
                continue
            image_info = output_info[key]['images'][0]  # note now only retrieve the first image
            image_path = image_info['filename']
            if image_info['subfolder']:
                image_path = f"{image_info['subfolder']}/{image_path}"

            record = await RecordRepository.retrieve_by_comfy_task_id(comfy_task_id)
            record.comfy_filepath = image_path
            await RecordRepository.update(record)

            # 2. retrieve the image from the comfy server
            view_uri = f'http://{self.endpoint}/view'
            params = {'filename': image_path}
            async with httpx.AsyncClient() as client:
                response = await client.get(view_uri, params=params)
                return response.content

    async def hook(self, record: Record):
        """callback to the client server"""
        uri = f'{self.callback_base_url}/{record.client_task_id}'
        async with httpx.AsyncClient() as client:
            response = await client.post(uri, json=record.to_dict())
            logger.debug(f'callback response: {response.text}')
            return response.json()

    async def clean_file(self, is_input: bool, image_path: str):
        """clean input or output file from the comfy server"""
        prompt = CLEAN_FILE_PROMPT_TEMPLATE.substitute(type='input' if is_input else 'output', path=image_path)
        prompt_json = json.loads(prompt)
        uri = f'http://{self.endpoint}/prompt'
        payload = {
            'prompt': prompt_json,
            # NOTE ignore client_id for now, in case of tracking the clean file system message
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(uri, json=payload)
            logger.debug(f'clean file response: {response.text}')

    async def upload_image(self, image: bytes):
        """upload image to the comfy server"""
        file_name = f'{uuid.uuid4()}.png'
        uri = f'http://{self.endpoint}/upload/image'
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(uri, files={'image': (file_name, image, 'image/jpeg')})
            logger.debug(f'upload image response: {response.text}')
            return response.json()

    async def store_failure(self, record: Record, image: bytes):
        """Store failure prompt result in the fallback path."""
        file_path = os.path.join(self.fallback_path, record.comfy_filepath)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(image)


comfy_servers = [ComfyServer(endpoint) for endpoint in COMFY_ENDPOINTS]