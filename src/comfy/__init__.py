import asyncio
import json
import logging
import os

import httpx
import websockets

from config import COMFY_HOST, COMFY_PORT, COMFY_CLIENT_ID, CALL_BACK_BASE_URL
from database import Record
from database.repository import RecordRepository
from s3 import upload_image_to_s3

logger = logging.getLogger(__name__)


class ComfyClient:
    _instance = None

    def __init__(self):
        self.host = COMFY_HOST
        self.port = COMFY_PORT
        self.client_id = COMFY_CLIENT_ID
        self.callback_base_url = CALL_BACK_BASE_URL

    @staticmethod
    def get_instance():
        if ComfyClient._instance is None:
            ComfyClient._instance = ComfyClient()
        return ComfyClient._instance

    async def queue_prompt(self, id, prompt: dict) -> Record:
        """commit a prompt to the comfy server"""
        uri = f'http://{self.host}:{self.port}/prompt'
        payload = {
            'prompt': prompt,
            'client_id': self.client_id
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(uri, json=payload)
            logger.debug(f'queue prompt response: {response.text}')
            prompt_id = response.json()['prompt_id']
            record = Record(id=id, prompt_id=prompt_id)
            record = await RecordRepository.create(record)
            return record

    async def listen(self):
        """listen messages from the comfy server"""
        uri = f'ws://{self.host}:{self.port}/ws?clientId={self.client_id}'
        async with websockets.connect(uri) as websocket:
            logger.info('connected to comfy server')
            while True:
                try:
                    message = await websocket.recv()
                    json_data = json.loads(message)
                    if json_data.get("type") == "executing" and json_data.get("data", {}).get("node") is None:
                        prompy_id = json_data['data']['prompt_id']
                        image = await self._retrieve_prompt(prompy_id)
                        s3_resp = await upload_image_to_s3(image)
                        logger.info(f'uploaded image to s3: {s3_resp}')
                        if s3_resp['success']:
                            record = await RecordRepository.retrieve_by_prompt_id(prompy_id)
                            record.s3_key = s3_resp['key']
                            record = await RecordRepository.update(record)
                            await self.hook(record)
                            # todo delete comfy image
                        else:
                            pass
                            # todo record failure locally
                except websockets.exceptions.ConnectionClosed:
                    logger.warning('connection closed, reconnecting...')
                    await asyncio.sleep(5)
                    websocket = await websockets.connect(uri)

    async def _retrieve_prompt(self, prompt_id: str) -> bytes:
        """retrieve a prompt from the comfy server"""
        history_uri = f'http://{self.host}:{self.port}/history/{prompt_id}'
        async with httpx.AsyncClient() as client:
            response = await client.get(history_uri)
            history = response.json()
        output_info = history[prompt_id]['outputs']
        for key in output_info:
            if 'images' not in output_info[key]:
                continue
            image_info = output_info[key]['images'][0]  # todo now only retrieve the first image
            image_path = image_info['filename']
            if image_info['subfolder']:
                image_path = f"{image_info['subfolder']}/{image_path}"

            record = await RecordRepository.retrieve_by_prompt_id(prompt_id)
            record.comfy_filepath = image_path
            await RecordRepository.update(record)
            return await self._process_image(image_path)


    async def _process_image(self, image_path: str) -> bytes:
        """retrieve image from the comfy server"""
        view_uri = f'http://{self.host}:{self.port}/view'
        params = {'filename': image_path}
        async with httpx.AsyncClient() as client:
            response = await client.get(view_uri, params=params)
            image = response.content
            return image

    async def hook(self, record: Record):
        """callback to the client server"""
        uri = f'{self.callback_base_url}/{record.id}'
        async with httpx.AsyncClient() as client:
            response = await client.post(uri, json=record.to_dict())
            logger.debug(f'callback response: {response.text}')
            return response.json()
