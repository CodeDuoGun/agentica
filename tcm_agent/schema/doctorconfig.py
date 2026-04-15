from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class DigitalDoctorConfig:
    video_frame: Optional[str]          # 数字人视频帧
    reference_audio: Optional[str]      # 参考音频
    video_url: Optional[str]            # 数字人视频
    tts_volume: Optional[float]         # 音量
    tts_emotion: Optional[str]          # 情绪
    pkl_path: Optional[str]             # pkl地址
    background_url: Optional[str]=None       # 背景地址
    slots: Optional[Dict[str, Any]]     # 槽位信息