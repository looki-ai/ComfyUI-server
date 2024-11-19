import base64
import json

from comfy import ComfyClient, logger
from database import Record
from workflows.img2img import IMG2IMG_PROMPT_TEMPLATE
from workflows.text2img import TEXT2IMG_PROMPT_TEMPLATE

comfy_client = ComfyClient.get_instance()

class Service:
    @staticmethod
    async def text2img(id: int, params: dict) -> Record:
        text = params.get('text')
        prompt_str = TEXT2IMG_PROMPT_TEMPLATE.substitute(text=text)
        prompt_json = json.loads(prompt_str)
        return await comfy_client.queue_prompt(id, prompt_json)

    @staticmethod
    async def img2img(id: int, params: dict) -> Record:
        text = params.get('text')
        image_base64 = params.get('image')

        # upload image to comfyui
        image_bytes = base64.b64decode(image_base64)
        resp = await comfy_client.upload_image(image_bytes)
        image_path = resp['name']
        if resp['subfolder']:
            image_path = f"{resp['subfolder']}/{image_path}"

        # create prompt
        prompt_str = IMG2IMG_PROMPT_TEMPLATE.substitute(text=text, image=image_path)
        prompt_json = json.loads(prompt_str)
        return await comfy_client.queue_prompt(id, prompt_json)


