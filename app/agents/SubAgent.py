from app.agents.BaseAgent import BaseAgent
from app.schemas.models import AttractionList, WeatherList, HotelList, ItineraryList


# --- 景点专家 ---
class AttractionAgent(BaseAgent):
    def __init__(self, tools, system_prompt, prompt_example):
        super().__init__(
            tools=tools,
            state_modifier=system_prompt,
            response_format=AttractionList,
            prompt_js=prompt_example,
        )


# --- 天气专家 ---
class WeatherAgent(BaseAgent):
    def __init__(self, tools, system_prompt, prompt_example):
        super().__init__(
            tools=tools,
            state_modifier=system_prompt,
            response_format=WeatherList,
            prompt_js=prompt_example,
        )


# --- 酒店专家 ---
class HotelAgent(BaseAgent):
    def __init__(self, tools, system_prompt, prompt_example):
        super().__init__(
            tools=tools,
            state_modifier=system_prompt,
            response_format=HotelList,
            prompt_js=prompt_example,
        )


# --- 行程专家 ---
class ItineraryAgent(BaseAgent):
    def __init__(self, tools, system_prompt, prompt_example):
        super().__init__(
            tools=tools,
            state_modifier=system_prompt,
            response_format=ItineraryList,
            prompt_js=prompt_example,
        )
