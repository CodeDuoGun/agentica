from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class DigitalDoctorConfig:
    video_frame: Optional[str] = None          # 数字人视频帧
    reference_audio: Optional[str] = None      # 参考音频
    video_url: Optional[str] = None            # 数字人视频
    tts_volume: Optional[float] = None         # 音量
    tts_emotion: Optional[str] = None          # 情绪
    pkl_path: Optional[str] = None             # pkl地址
    slots: Optional[Dict[str, Any]] = None     # 槽位信息
    background_url: Optional[str] = None       # 背景地址