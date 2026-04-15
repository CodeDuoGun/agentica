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
    base_url: str="",
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
    mock_data = {
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
                {"name": "visit_type", "required": True, "definition": "就诊类型（初诊/复诊等）"},
                {"name": "gender", "required": True, "definition": "患者性别"},
                {"name": "age", "required": True, "definition": "患者年龄"}
            ],
            "chief_complaint": [
                {"name": "severity", "required": True, "definition": "症状严重程度"},
                {"name": "location", "required": True, "definition": "症状发生部位"},
                {"name": "duration", "required": True, "definition": "症状持续时间"},
                {"name": "trigger", "required": True, "definition": "诱发或加重因素"},
                {"name": "relief", "required": True, "definition": "缓解因素"}
            ],
            "symptom_detail": [
                {"name": "ask_pain", "required": False, "definition": "疼痛相关情况（性质、程度等）"},
                {"name": "ask_digest", "required": False, "definition": "消化系统相关症状（食欲、反酸等）"},
                {"name": "ask_sleep", "required": True, "definition": "睡眠情况（入睡、梦境等）"},
                {"name": "ask_stool", "required": True, "definition": "二便,大便和小便情况如何？是否有便秘、腹泻或小便异常？"},
                {"name": "ask_urine", "required": True, "definition": "饮食情况近期食欲如何？进食量有没有变化？有无口味异常或厌食？"},
                {"name": "ask_medicine", "required": True, "definition": "近期是否服用过药物？用药后症状是否有变化？"},
                {"name": "ask_menstruation", "required": False, "definition": "患者为女性时必须询问月经情况如何？周期是否规律？有无提前、推迟或异常出血？"}
            ],
            "history": [
                {"name": "past_history", "required": True, "definition": "既往疾病史"},
                {"name": "allergy", "required": True, "definition": "过敏史"},
                {"name": "marriage", "required": True, "definition": "婚育史"},
                {"name": "personal", "required": True, "definition": "个人史（生活习惯等）"},
                {"name": "family", "required": True, "definition": "家族史"}
            ],
            "imgs": [
                {"name": "tongue", "required": False, "definition": "舌象图片"},
                {"name": "tongue_analysis", "required": False, "definition": "舌象分析结果"},
                {"name": "face", "required": False, "definition": "面部图像"},
                {"name": "face_analysis", "required": False, "definition": "面部分析结果"},
                {"name": "exam_report", "required": False, "definition": "检查报告图片或文件"},
                {"name": "exam_analysis", "required": False, "definition": "检查报告分析结果"},
                {"name": "supplementary", "required": True, "definition": "补充资料（其他辅助信息）"}
            ]
        }
    }

    return DigitalDoctorConfig(
        video_frame=mock_data.get("video_frame"),
        reference_audio=mock_data.get("reference_audio"),
        video_url=mock_data.get("video_url"),
        tts_volume=mock_data.get("tts", {}).get("volume"),
        tts_emotion=mock_data.get("tts", {}).get("emotion"),
        pkl_path=mock_data.get("pkl_path"),
        background_url=mock_data.get("background_url"),
        slots=mock_data.get("slots"),
    )

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