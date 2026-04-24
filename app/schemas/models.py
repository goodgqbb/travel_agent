from pydantic import BaseModel, Field, AliasChoices
from typing import List, Optional, Literal


# --- 景点模型 ---
class Attraction(BaseModel):
    """单个景点的详细信息"""
    name: str = Field(description="景点名称")
    location: str = Field(description="景点的大致方位或具体地址")
    poi_id: str = Field(description="【必填】高德地图POI ID (如 B0xxx)。严禁填写'无'、'未知'或留空！如果你不知道，必须先调用地图搜索工具查询！")
    recommended_time: Optional[str] = Field(description="建议游玩时长（如：半天、2-3小时）")
    highlight: Optional[str] = Field(description="景点核心特色（不超过30个字）")
    reason: Optional[str] = Field(description="推荐理由及游玩建议")


class AttractionList(BaseModel):
    """这是一个包含多个景点的列表对象"""
    attractionList: List[Attraction] = Field(description="推荐的景点列表对象，默认推荐5-7个",
                                             validation_alias=AliasChoices('attractionList', 'recommendations',
                                                                           'results', 'list'))


# --- 天气模型 ---
class Weather(BaseModel):
    """单个天气的详细信息"""
    date: str = Field(description="日期（如：周六、2024-05-01）")
    weather: str = Field(description="天气状况（如：晴转多云、中雨）")
    temperature: str = Field(description="气温范围（如：15℃ - 25℃）")
    dress_code: Optional[str] = Field(description="穿衣建议")
    tips: Optional[str] = Field(description="防晒/防雨等特殊出行提醒")


class WeatherList(BaseModel):
    """这是一个包含多个天气信息的列表对象"""
    weatherList: List[Weather] = Field(description="包含出行时间和游玩时间的天气预报列表对象")


# --- 酒店模型 ---
class Hotel(BaseModel):
    """单个酒店的详细信息"""
    name: str = Field(description="酒店名称")
    location: str = Field(description="大致位置（如：近洪崖洞、解放碑商圈）")
    price_estimate: str = Field(description="预估价格范围（如：300-500元/晚，若查不到填'未知'）")
    rating: Optional[str] = Field(description="评分或星级（如：4.5分、高档型）")
    advantage: Optional[str] = Field(description="核心优势（如：交通便利、江景房）")


class HotelList(BaseModel):
    """这是一个包含多个酒店信息的列表对象"""
    hotelList: List[Hotel] = Field(description="符合用户预算和位置要求的酒店列表对象")


# --- 行程模型 ---
class ScheduleItem(BaseModel):
    """单个行程的详细信息"""
    time: str = Field(description="时间段（如：09:00 - 12:00）")
    activity: str = Field(description="具体活动安排及所去景点")
    logistics: str = Field(description="交通建议或耗时预估")
    tips: str = Field(description="温馨提示（结合天气穿衣、避坑指南、餐饮推荐等）")


class DailyItinerary(BaseModel):
    """一天行程的详细信息"""
    day: str = Field(description="第几天（如：Day 1、周六）")
    theme: str = Field(description="当日游玩主题（如：山城夜景之旅、休闲徒步）")
    schedule: List[ScheduleItem] = Field(description="当日具体的时间段行程安排的列表对象")


class ItineraryList(BaseModel):
    """多日行程的详细信息的列表对象"""
    itineraryList: List[DailyItinerary] = Field(description="完整的多日游玩路线")


class AnalyzerResult(BaseModel):
    """分析器输出结构"""
    extracted_time: Optional[str] = Field(description="提取到的游玩时间，如无填 'null'")
    departure: Optional[str] = Field(description="提取到的【出发位置】（用户当前在哪）。如果用户只说了去哪没说从哪出发，必须填 'null'，严禁脑补！")
    destination: Optional[str] = Field(description="提取到的【目的位置】（用户要去哪玩）。如无填 'null'")
    is_complete: bool = Field(description="信息是否完整，是否满足规划需求")
    suggested_question: Optional[str] = Field(default=None, description="如果不完整，建议询问的问题")
    extract_requirements: Optional[str] = Field(default=None, description="从问题中提取的具体要求")


class Multi_Result(BaseModel):
    """分析多模态输入"""
    location: Optional[str] = Field(description="提取到的想去的游玩地点，如无填 'null'")
    atmosphere: Optional[str] = Field(description="提取到的景点的环境氛围，如无填 'null'")
    constraints: Optional[str] = Field(description="提取到的景点的要求（比如禁止宠物携带，或者爬山要求比较好的体力等），如无填 'null'")


# 定义 Supervisor 必须输出的格式
class RouteDecision(BaseModel):
    next_node: Literal["WeatherAgent", "AttractionAgent", "HotelAgent", "ItineraryAgent", "FINISH"] = Field(
        description="决定下一个要调用的 Agent。如果需要天气选 WeatherAgent；景点选 AttractionAgent；酒店选 HotelAgent。规划行程 ItineraryAgent。选如果规划完成或要回复用户选 FINISH。"
    )
    reply_to_user: str = Field(
        default="",
        description="如果选择了 FINISH，请在这里写下给用户的汇总回复。如果是调用其他 Agent，这里留空。"
    )
