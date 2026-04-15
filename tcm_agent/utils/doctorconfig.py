"""根据doctor_id 获取数字人医生形象相关配置
1、数字人视频帧
2、数字人参考音频
3、数字人视频
4、tts 音量、情绪
5、数字人pkl地址
6、数字人背景地址，默认关闭
7、数字人槽位信息json
"""

import requests
from tcm_agent.schema.doctorconfig import DigitalDoctorConfig


def get_digital_doctor_config(
    doctor_id: str,
    gender: str,
    age: int,
    base_url: str,
    timeout: int = 10
) -> DigitalDoctorConfig:
    """
    获取数字人医生配置

    :param doctor_id: 医生ID
    :param gender: 患者性别（male/female）
    :param age: 患者年龄
    :param base_url
    :param timeout: 请求超时时间
    """
    #  返回mock数据
    return  {
        "doctor_id": "doctor_001",
        "video_frame": "https://cdn.xxx.com/avatar/doctor_001/frame.png",
        "reference_audio": "https://cdn.xxx.com/avatar/doctor_001/ref_audio.wav",
        "video_url": "https://cdn.xxx.com/avatar/doctor_001/intro.mp4",
        "tts": {
        "volume": 0.85,
        "emotion": "calm"
        },
        "pkl_path": "https://cdn.xxx.com/avatar/doctor_001/model.pkl",
        "background_url": None,
        "slots": {
            "patient": [
                { "name": "visit_type", "required": True},
                { "name": "gender", "required": True},
                { "name": "age", "required": True}
            ],
            "chief_complaint": [
                { "name": "severity", "required": True },
                { "name": "location", "required": True },
                { "name": "duration", "required": True },
                { "name": "trigger", "required": True },
                { "name": "relief", "required": True }
            ],
            "symptom_detail": [
                { "name": "ask_pain", "required": False },
                { "name": "ask_digest", "required": False },
                { "name": "ask_sleep", "required": False },
                { "name": "ask_stool", "required": True },
                { "name": "ask_urine", "required": True }
            ],
            "history": [
                { "name": "past_history", "required": True },
                { "name": "allergy", "required": True },
                { "name": "marriage", "required": True },
                { "name": "personal", "required": True },
                { "name": "family", "required": True },
            ],
            "imgs": [
                { "name": "tongue", "required": False},
                {"name": "tongue_analysis", "required": False},
                { "name": "face", "required": False},
                {"name": "face_analysis", "required": False},
                { "name": "exam_report", "required":False},
                {"name": "exam_analysis", "required": False},
                { "name": "supplementary", "required": True},

            ]
        }
    }


    url = f"{base_url}/digital-doctor/config"

    payload = {
        "doctor_id": doctor_id,
        "gender": gender,
        "age": age
    }

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"请求数字人配置失败: {e}")

    # {
    #   "code": 0,
    #   "data": {...}
    # }

    if data.get("code") != 0:
        raise ValueError(f"接口返回错误: {data}")

    d = data.get("data", {})

    return DigitalDoctorConfig(
        video_frame=d.get("video_frame"),
        reference_audio=d.get("reference_audio"),
        video_url=d.get("video_url"),
        tts_volume=d.get("tts", {}).get("volume"),
        tts_emotion=d.get("tts", {}).get("emotion"),
        pkl_path=d.get("pkl_path"),
        background_url=d.get("background_url"),
        slots=d.get("slots")
    )