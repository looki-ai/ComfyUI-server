import json

from comfy import ComfyClient
from database import Record
from workflows.text2img import TEXT2IMG_PROMPT_TEMPLATE

comfy_client = ComfyClient.get_instance()

class Service:
    @staticmethod
    async def text2img(id: int, params: dict) -> Record:
        text = params.get('text')
        prompt_str = TEXT2IMG_PROMPT_TEMPLATE.substitute(text=text)
        prompt_json = json.loads(prompt_str)
        return await comfy_client.queue_prompt(id, prompt_json)


