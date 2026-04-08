// ==================== 状态管理 ====================
let currentSessionId = null;
let isRecording = false;
let recognition = null;
let recordingTimer = null;
let recordingSeconds = 0;
let isProcessing = false;
let currentAssistantMessage = null;

// ==================== 就诊人管理 ====================
let selectedPatient = null;
let patientsList = [];

// ==================== 图片上传状态 ====================
const imageState = {
    tongue: { file: null, url: null, analysis: null },
    face: { file: null, url: null, analysis: null },
    report: { file: null, url: null, analysis: null }
};
let currentImageRequest = null;

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('messageInput');

    if (messageInput) {
        messageInput.addEventListener('input', () => {
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        });

        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    initVoiceRecognition();
    loadPatients();
    hideInputArea();
});

// ==================== 就诊人选择 ====================
async function loadPatients() {
    try {
        const response = await fetch('/api/patients');
        if (response.ok) {
            const data = await response.json();
            patientsList = data.patients || [];
            renderPatientList();
        }
    } catch (error) {
        console.error('获取就诊人列表失败:', error);
        patientsList = getDefaultPatients();
        renderPatientList();
    }
}

function getDefaultPatients() {
    return [
        { id: 1, name: '张三', gender: '男', age: 35, phone: '138****1234' },
        { id: 2, name: '李四', gender: '女', age: 28, phone: '139****5678' },
        { id: 3, name: '王五', gender: '男', age: 45, phone: '137****9012' }
    ];
}

function renderPatientList() {
    const patientListEl = document.getElementById('patientList');
    if (!patientListEl) return;

    if (patientsList.length === 0) {
        patientListEl.innerHTML = '<div class="patient-empty">暂无预设就诊人，可手动添加</div>';
        return;
    }

    patientListEl.innerHTML = patientsList.map(patient => `
        <div class="patient-item" onclick='selectPatient(${JSON.stringify(String(patient.id))})'>
            <div class="patient-item-name">${escapeHtml(patient.name)}</div>
            <div class="patient-item-detail">${patient.gender} | ${patient.age}岁 | ${patient.phone || ''}</div>
        </div>
    `).join('');
}

function togglePatientSelect() {
    const patientListEl = document.getElementById('patientList');
    if (patientListEl) {
        patientListEl.classList.toggle('show');
    }
}

function toggleManualPatientForm() {
    const formEl = document.getElementById('manualPatientForm');
    const toggleEl = document.getElementById('manualPatientToggle');
    const patientListEl = document.getElementById('patientList');
    if (!formEl || !toggleEl) return;

    const isVisible = formEl.style.display === 'block';
    formEl.style.display = isVisible ? 'none' : 'block';
    toggleEl.textContent = isVisible ? '+ 添加就诊人' : '收起添加';
    if (!isVisible && patientListEl) {
        patientListEl.classList.remove('show');
    }
}

function resetManualPatientForm() {
    const fields = ['manualPatientName', 'manualPatientGender', 'manualPatientAge', 'manualPatientPhone'];
    fields.forEach((id) => {
        const field = document.getElementById(id);
        if (field) field.value = '';
    });
}

function cancelManualPatient() {
    const formEl = document.getElementById('manualPatientForm');
    const toggleEl = document.getElementById('manualPatientToggle');
    if (formEl) formEl.style.display = 'none';
    if (toggleEl) toggleEl.textContent = '+ 添加就诊人';
    resetManualPatientForm();
}

function saveManualPatient() {
    const name = document.getElementById('manualPatientName')?.value.trim() || '';
    const gender = document.getElementById('manualPatientGender')?.value || '';
    const ageValue = document.getElementById('manualPatientAge')?.value || '';
    const phone = document.getElementById('manualPatientPhone')?.value.trim() || '';

    if (!name || !gender || !ageValue || !phone) {
        alert('请完整填写姓名、性别、年龄和手机号');
        return;
    }

    const age = Number(ageValue);
    if (!Number.isInteger(age) || age <= 0 || age > 120) {
        alert('请输入正确的年龄');
        return;
    }

    if (!/^1\d{10}$/.test(phone)) {
        alert('请输入正确的 11 位手机号');
        return;
    }

    const manualPatient = {
        id: `manual-${Date.now()}`,
        name,
        gender,
        age,
        phone,
        isManual: true
    };

    patientsList = [manualPatient, ...patientsList.filter(patient => !patient.isManual)];
    renderPatientList();
    cancelManualPatient();
    selectedPatient = manualPatient;
    applySelectedPatient();
}

function applySelectedPatient() {
    if (!selectedPatient) return;

    const patientListEl = document.getElementById('patientList');
    const patientSelectArea = document.getElementById('patientSelectArea');
    const patientSelectedInfo = document.getElementById('patientSelectedInfo');
    const selectedPatientName = document.getElementById('selectedPatientName');
    const selectedPatientDetail = document.getElementById('selectedPatientDetail');

    if (patientListEl) patientListEl.classList.remove('show');
    if (patientSelectArea) patientSelectArea.style.display = 'none';
    if (patientSelectedInfo) patientSelectedInfo.style.display = 'flex';
    if (selectedPatientName) selectedPatientName.textContent = selectedPatient.name;
    if (selectedPatientDetail) {
        selectedPatientDetail.textContent = `${selectedPatient.gender} | ${selectedPatient.age}岁 | ${selectedPatient.phone || ''}`;
    }

    newSession();
}

function selectPatient(patientId) {
    selectedPatient = patientsList.find(p => String(p.id) === String(patientId));
    if (!selectedPatient) return;

    applySelectedPatient();
}

function changePatient() {
    selectedPatient = null;
    const patientSelectArea = document.getElementById('patientSelectArea');
    const patientSelectedInfo = document.getElementById('patientSelectedInfo');
    const patientSelectText = document.getElementById('patientSelectText');

    if (patientSelectArea) patientSelectArea.style.display = 'block';
    if (patientSelectedInfo) patientSelectedInfo.style.display = 'none';
    if (patientSelectText) patientSelectText.textContent = '请选择';
    cancelManualPatient();
}

function hideInputArea() {
    const inputArea = document.querySelector('.input-area');
    if (inputArea) inputArea.style.display = 'none';
}

function showInputArea() {
    const inputArea = document.querySelector('.input-area');
    if (inputArea) inputArea.style.display = 'block';
}

function handleNewSessionBtn() {
    selectedPatient = null;
    const patientSelectArea = document.getElementById('patientSelectArea');
    const patientSelectedInfo = document.getElementById('patientSelectedInfo');
    const patientSelectText = document.getElementById('patientSelectText');

    if (patientSelectArea) patientSelectArea.style.display = 'block';
    if (patientSelectedInfo) patientSelectedInfo.style.display = 'none';
    if (patientSelectText) patientSelectText.textContent = '请选择';

    cancelManualPatient();
    hideInputArea();

    const messagesEl = document.getElementById('messages');
    if (messagesEl) {
        messagesEl.innerHTML = `
            <div class="empty-state" id="emptyState">
                <div class="empty-state-icon">🩺</div>
                <p>欢迎使用中医智能问诊系统</p>
                <span>请先选择就诊人，然后开始咨询</span>
            </div>
        `;
    }

    const sessionIdEl = document.getElementById('sessionId');
    if (sessionIdEl) sessionIdEl.textContent = '会话ID: --';

    const visitTypeInfo = document.getElementById('visitTypeInfo');
    if (visitTypeInfo) visitTypeInfo.textContent = '类型: --';

    const phaseInfo = document.getElementById('phaseInfo');
    if (phaseInfo) phaseInfo.textContent = '阶段: 欢迎';

    currentSessionId = null;
}

// ==================== 会话管理 ====================
async function newSession() {
    try {
        clearAllImages();
        currentImageRequest = null;
        updateImageUploadArea(null);

        const doctorId = 1;

        let visitType = 'first_visit';
        let patientData = null;

        if (selectedPatient) {
            visitType = 'follow_up_visit';
            patientData = {
                name: selectedPatient.name,
                gender: selectedPatient.gender,
                age: selectedPatient.age
            };
        }

        const requestBody = {
            visit_type: visitType,
            doctor_id: doctorId,
            patient_data: patientData
        };

        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) throw new Error('创建会话失败');

        const data = await response.json();
        currentSessionId = data.session_id;

        const sessionIdEl = document.getElementById('sessionId');
        if (sessionIdEl) {
            sessionIdEl.textContent = `会话ID: ${currentSessionId.slice(0, 8)}...`;
        }

        const messagesEl = document.getElementById('messages');
        if (messagesEl) {
            messagesEl.innerHTML = '';
        }

        const visitTypeInfo = document.getElementById('visitTypeInfo');
        if (visitTypeInfo) {
            visitTypeInfo.textContent = `类型: ${visitType === 'first_visit' ? '初诊' : '复诊'}`;
        }

        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.style.display = 'none';

        showInputArea();

        if (data.welcome_message) {
            addMessage('assistant', data.welcome_message);
        }

    } catch (error) {
        console.error('创建会话失败:', error);
        alert('创建会话失败，请刷新页面重试');
    }
}

async function getSessionInfo(sessionId) {
    try {
        const response = await fetch(`/api/sessions/${sessionId}`);
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('获取会话信息失败:', error);
        return null;
    }
}

// ==================== 消息处理 ====================
async function sendMessage() {
    const input = document.getElementById('messageInput');
    if (!input) return;
    
    const message = input.value.trim();
    const hasImages = hasPendingImages();

    if (!message && !hasImages) return;
    if (!currentSessionId || isProcessing) return;

    input.value = '';
    input.style.height = 'auto';

    if (message) {
        addMessage('user', message);
    }

    if (hasImages) {
        const displayMessage = message || '已上传图片';
        if (!message) {
            addMessage('user', displayMessage);
        }

        const prevInlineArea = document.querySelector('.inline-image-request');
        if (prevInlineArea) {
            prevInlineArea.remove();
        }
    }

    showTypingIndicator();
    isProcessing = true;
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) sendBtn.disabled = true;

    try {
        const requestData = {
            session_id: currentSessionId,
            message: message || '',
            imgs: getImagesData()
        };

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) throw new Error('发送消息失败');

        hideTypingIndicator();
        currentAssistantMessage = createAssistantMessage();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let done = false;

        while (!done) {
            const { value, done: streamDone } = await reader.read();
            done = streamDone;
            if (value) {
                buffer += decoder.decode(value, { stream: !done });
                processSSEBuffer(buffer, (eventData) => {
                    handleSSEMessage(eventData);
                }, (remaining) => {
                    buffer = remaining;
                });
            }
        }

        if (buffer.trim()) {
            try {
                const eventData = JSON.parse(buffer.replace(/^data: /, ''));
                handleSSEMessage(eventData);
            } catch (e) {
                console.error('解析最终 SSE 数据失败:', e, 'buffer:', buffer);
            }
        }

        finalizeAssistantMessage();
        clearSentImages();

    } catch (error) {
        console.error('发送消息失败:', error);
        hideTypingIndicator();
        addMessage('assistant', '抱歉，发送消息失败了。请稍后重试。');
    } finally {
        isProcessing = false;
        const sendBtn = document.getElementById('sendBtn');
        if (sendBtn) sendBtn.disabled = false;
        currentAssistantMessage = null;
    }
}

function processSSEBuffer(buffer, onEvent, onRemaining) {
    const lines = buffer.split('\n');
    let dataLine = '';
    let hasCompleteEvent = false;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.startsWith('data: ')) {
            dataLine = line.slice(6);
            hasCompleteEvent = true;
        } else if (line.trim() === '' && hasCompleteEvent) {
            try {
                const eventData = JSON.parse(dataLine);
                onEvent(eventData);
            } catch (e) {
                console.error('解析 SSE 数据失败:', e);
            }
            dataLine = '';
            hasCompleteEvent = false;
        }
    }

    if (dataLine) {
        onRemaining(dataLine);
    } else if (lines[lines.length - 1].trim() !== '' && lines[lines.length - 1].trim().startsWith('data: ')) {
        onRemaining(lines[lines.length - 1]);
    } else {
        onRemaining('');
    }
}

function handleSSEMessage(data) {
    const { event, msg_type, content, phase } = data;

    switch (event) {
        case 'start':
            break;

        case 'text':
            if (msg_type === 'text' && content) {
                appendToAssistantMessage(content);
            }
            break;

        case 'done':
            if (phase) {
                const phaseInfo = document.getElementById('phaseInfo');
                if (phaseInfo) {
                    phaseInfo.textContent = `阶段: ${getPhaseName(phase)}`;
                }
            }
            break;

        case 'error':
            if (content) {
                appendToAssistantMessage('\n\n[错误] ' + content);
            }
            break;
    }
}

function createAssistantMessage() {
    const messagesContainer = document.getElementById('messages');
    const emptyState = document.getElementById('emptyState');

    if (emptyState) {
        emptyState.style.display = 'none';
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-avatar">🧑‍⚕️</div>
        <div class="message-content">
            <div class="message-text"></div>
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return messageDiv;
}

function appendToAssistantMessage(text) {
    if (!currentAssistantMessage) return;

    const textDiv = currentAssistantMessage.querySelector('.message-text');
    if (textDiv) {
        textDiv.textContent += text;
    }

    const messagesContainer = document.getElementById('messages');
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function finalizeAssistantMessage() {
    if (!currentAssistantMessage) return;

    const textDiv = currentAssistantMessage.querySelector('.message-text');
    const text = textDiv ? textDiv.textContent : '';

    const imageRequest = parseImageRequest(text);
    const cleanText = cleanResponseText(text);

    if (textDiv) {
        textDiv.textContent = cleanText;
    }

    if (imageRequest) {
        const contentDiv = currentAssistantMessage.querySelector('.message-content');
        const inlineArea = document.createElement('div');
        inlineArea.className = 'inline-image-request';
        inlineArea.id = 'inlineUploadArea';
        contentDiv.appendChild(inlineArea);

        renderInlineUploadButtons(imageRequest);
    }
}

function hasPendingImages() {
    return Object.values(imageState).some(s => s.file !== null);
}

function clearSentImages() {
    ['tongue', 'face', 'report'].forEach(type => {
        if (imageState[type].file) {
            imageState[type].file = null;
            imageState[type].url = null;
        }
    });
}

function sendQuickMessage(message) {
    const input = document.getElementById('messageInput');
    if (input) {
        input.value = message;
        sendMessage();
    }
}

function addMessage(role, content) {
    const messagesContainer = document.getElementById('messages');
    const emptyState = document.getElementById('emptyState');

    if (emptyState) {
        emptyState.style.display = 'none';
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🧑‍⚕️';

    const imageRequest = role === 'assistant' ? parseImageRequest(content) : null;
    const cleanContent = role === 'assistant' ? cleanResponseText(content) : content;

    messageDiv.innerHTML = `
        ${role === 'assistant' ? `<div class="message-avatar">${avatar}</div>` : ''}
        <div class="message-content">
            <div class="message-text">${escapeHtml(cleanContent)}</div>
            ${imageRequest ? `<div class="inline-image-request" id="inlineUploadArea"></div>` : ''}
        </div>
        ${role === 'user' ? `<div class="message-avatar">${avatar}</div>` : ''}
    `;

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    if (imageRequest) {
        renderInlineUploadButtons(imageRequest);
    }
}

function renderInlineUploadButtons(imageRequest) {
    const area = document.getElementById('inlineUploadArea');
    if (!area) return;

    const titles = { tongue: '舌照', face: '面照', report: '检查报告' };
    const icons = { tongue: '👅', face: '😊', report: '📋' };
    const descs = {
        tongue: '点击上传舌面照片',
        face: '点击上传面照',
        report: '上传检查报告'
    };

    const btn = document.createElement('div');
    btn.className = `inline-upload-btn ${imageState[imageRequest].file ? 'has-image' : 'requested'}`;
    btn.onclick = () => triggerImageUpload(imageRequest);

    const existingPreview = imageState[imageRequest].url;
    const previewHtml = existingPreview
        ? `<div class="inline-upload-container">
               <img src="${existingPreview}" class="inline-upload-preview" alt="${titles[imageRequest]}">
               <button class="inline-upload-remove" onclick="event.stopPropagation(); removeImage('${imageRequest}'); renderInlineUploadButtons('${imageRequest}');">×</button>
           </div>`
        : '';

    btn.innerHTML = `
        <input type="file" id="inline${imageRequest}Input" accept="image/*" onchange="handleInlineImageUpload(this, '${imageRequest}')">
        ${previewHtml || `<div class="icon">${icons[imageRequest]}</div>`}
        <div class="title">${titles[imageRequest]}</div>
        <div class="desc">${existingPreview ? '点击更换' : descs[imageRequest]}</div>
    `;

    area.appendChild(btn);

    if (!imageState[imageRequest].file) {
        const submitBtn = document.createElement('button');
        submitBtn.className = 'inline-submit-btn';
        submitBtn.innerHTML = '📤 上传图片继续';
        submitBtn.onclick = () => {
            if (imageState[imageRequest].file) {
                submitInlineImage(imageRequest);
            } else {
                triggerImageUpload(imageRequest);
            }
        };
        area.appendChild(submitBtn);
    }
}

function handleInlineImageUpload(input, type) {
    const file = input.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        alert('请上传图片文件');
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        alert('图片大小不能超过 10MB');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        imageState[type].file = file;
        imageState[type].url = e.target.result;
        renderInlineUploadButtons(type);
    };
    reader.readAsDataURL(file);
}

function submitInlineImage(type) {
    const message = '好的，已上传图片';
    const input = document.getElementById('messageInput');
    if (input) {
        input.value = message;
        sendMessage();
    }
}

function showTypingIndicator() {
    const messagesContainer = document.getElementById('messages');
    const indicator = document.createElement('div');
    indicator.id = 'typingIndicator';
    indicator.className = 'message assistant';
    indicator.innerHTML = `
        <div class="message-avatar">🧑‍⚕️</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

function getPhaseName(phase) {
    const phaseNames = {
        'WELCOME': '欢迎',
        'SYMPTOM_COLLECTION': '症状收集',
        'MEDICAL_HISTORY': '病史询问',
        'PHYSICAL_EXAM': '体格检查',
        'TONGUE_PULSE': '舌脉诊断',
        'DIAGNOSIS': '诊断',
        'TREATMENT': '治疗方案',
        'COMPLETE': '完成'
    };
    return phaseNames[phase] || phase;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 语音识别 ====================
function initVoiceRecognition() {
    const voiceBtn = document.getElementById('voiceBtn');
    if (!voiceBtn) return;
    
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        voiceBtn.title = '浏览器不支持语音输入';
        voiceBtn.style.opacity = '0.5';
        voiceBtn.style.pointerEvents = 'none';
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        const input = document.getElementById('messageInput');
        if (input) input.value = transcript;
    };

    recognition.onend = () => {
        if (isRecording) {
            recognition.start();
        }
    };

    recognition.onerror = (event) => {
        console.error('语音识别错误:', event.error);
        stopRecording();
    };

    voiceBtn.addEventListener('click', toggleRecording);
}

function toggleRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

function startRecording() {
    if (!recognition) return;
    
    isRecording = true;
    const voiceBtn = document.getElementById('voiceBtn');
    if (voiceBtn) {
        voiceBtn.classList.add('recording');
        voiceBtn.textContent = '⏹';
    }
    
    const recordingTime = document.getElementById('recordingTime');
    if (recordingTime) recordingTime.style.display = 'flex';
    recordingSeconds = 0;
    updateRecordingTime();
    recordingTimer = setInterval(updateRecordingTime, 1000);
    
    const input = document.getElementById('messageInput');
    if (input) input.value = '';
    
    try {
        recognition.start();
    } catch (error) {
        console.error('启动语音识别失败:', error);
        stopRecording();
    }
}

function stopRecording() {
    if (!recognition) return;
    
    isRecording = false;
    const voiceBtn = document.getElementById('voiceBtn');
    if (voiceBtn) {
        voiceBtn.classList.remove('recording');
        voiceBtn.textContent = '🎤';
    }
    
    const recordingTime = document.getElementById('recordingTime');
    if (recordingTime) recordingTime.style.display = 'none';
    if (recordingTimer) {
        clearInterval(recordingTimer);
        recordingTimer = null;
    }
    
    try {
        recognition.stop();
    } catch (error) {
        console.error('停止语音识别失败:', error);
    }
}

function updateRecordingTime() {
    recordingSeconds++;
    const minutes = Math.floor(recordingSeconds / 60);
    const seconds = recordingSeconds % 60;
    const durationEl = document.getElementById('recordingDuration');
    if (durationEl) {
        durationEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
}

// ==================== 图片上传处理 ====================
function triggerImageUpload(type) {
    const inputId = `${type}Input`;
    const input = document.getElementById(inputId);
    if (input) input.click();
}

function handleImageUpload(input, type) {
    const file = input.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        alert('请上传图片文件');
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        alert('图片大小不能超过 10MB');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const dataUrl = e.target.result;

        imageState[type].file = file;
        imageState[type].url = dataUrl;

        updateImageCard(type, dataUrl);
        showImageAnalysisLoading(type);
    };
    reader.readAsDataURL(file);
}

function updateImageCard(type, dataUrl) {
    const cardId = `${type}UploadCard`;
    const descId = `${type}Desc`;
    const card = document.getElementById(cardId);
    const desc = document.getElementById(descId);

    if (card) card.classList.add('has-image');

    const iconNames = { tongue: '👅', face: '😊', report: '📋' };
    const titles = { tongue: '舌照', face: '面照', report: '检查报告' };

    if (card) {
        card.innerHTML = `
            <div class="image-preview-container">
                <img src="${dataUrl}" class="image-preview" alt="${titles[type]}">
                <button class="image-remove-btn" onclick="event.stopPropagation(); removeImage('${type}')">×</button>
            </div>
            <div class="image-upload-title">${titles[type]}</div>
            <div class="image-upload-desc" id="${descId}">点击更换</div>
            <div class="image-analysis-result" id="${type}AnalysisResult" style="display: none;"></div>
            <input type="file" id="${type}Input" accept="image/*" onchange="handleImageUpload(this, '${type}')" style="display: none;">
        `;
    }
}

function showImageAnalysisLoading(type) {
    const resultId = `${type}AnalysisResult`;
    let resultEl = document.getElementById(resultId);

    if (!resultEl) {
        const card = document.getElementById(`${type}UploadCard`);
        if (card) {
            resultEl = document.createElement('div');
            resultEl.className = 'image-analysis-result';
            resultEl.id = resultId;
            card.appendChild(resultEl);
        }
    }

    if (resultEl) {
        resultEl.style.display = 'block';
        resultEl.innerHTML = '<span class="image-analysis-loading">正在分析...</span>';
    }
}

function showImageAnalysisResult(type, analysis) {
    const resultId = `${type}AnalysisResult`;
    const resultEl = document.getElementById(resultId);
    if (resultEl) {
        resultEl.innerHTML = `<strong>分析结果：</strong>${escapeHtml(analysis)}`;
    }

    imageState[type].analysis = analysis;
}

function removeImage(type) {
    imageState[type] = { file: null, url: null, analysis: null };

    const cardId = `${type}UploadCard`;
    const card = document.getElementById(cardId);
    const iconNames = { tongue: '👅', face: '😊', report: '📋' };
    const titles = { tongue: '舌照', face: '面照', report: '检查报告' };
    const descs = {
        tongue: '点击上传舌面照',
        face: '点击上传面照',
        report: '点击上传报告'
    };

    if (card) {
        card.classList.remove('has-image');
        card.innerHTML = `
            <input type="file" id="${type}Input" accept="image/*" onchange="handleImageUpload(this, '${type}')">
            <div class="image-upload-icon">${iconNames[type]}</div>
            <div class="image-upload-title">${titles[type]}</div>
            <div class="image-upload-desc" id="${type}Desc">${descs[type]}</div>
        `;
    }

    if (currentImageRequest === type) {
        setTimeout(() => triggerImageUpload(type), 300);
    }
}

function updateImageUploadArea(imageRequest) {
    const area = document.getElementById('imageUploadArea');
    const hint = document.getElementById('imageUploadHint');
    const tongueCard = document.getElementById('tongueUploadCard');
    const faceCard = document.getElementById('faceUploadCard');
    const reportCard = document.getElementById('reportUploadCard');

    currentImageRequest = imageRequest;

    if (!area) return;

    if (imageRequest) {
        area.classList.add('active');

        const hints = {
            tongue: '请上传舌面照片，包括舌上和舌下',
            face: '请上传面部照片',
            report: '如有检查报告也可上传'
        };
        if (hint) hint.textContent = hints[imageRequest] || '请上传图片';

        [tongueCard, faceCard, reportCard].forEach(card => {
            if (card) card.classList.remove('requested');
        });

        const cardMap = { tongue: tongueCard, face: faceCard, report: reportCard };
        if (cardMap[imageRequest]) {
            cardMap[imageRequest].classList.add('requested');
        }

        if (imageState[imageRequest].file) {
            if (hint) hint.textContent = `${imageRequest === 'tongue' ? '舌照' : imageRequest === 'face' ? '面照' : '检查报告'}已上传`;
            if (cardMap[imageRequest]) {
                cardMap[imageRequest].classList.remove('requested');
            }
        }
    } else {
        const hasAnyImage = Object.values(imageState).some(s => s.file !== null);
        if (hasAnyImage) {
            area.classList.add('active');
            if (hint) hint.textContent = '已上传的图片将随消息发送';
        } else {
            area.classList.remove('active');
        }
    }
}

function parseImageRequest(response) {
    const match = response.match(/\[IMAGE_REQUEST:(tongue|face|report)\]/);
    if (match) {
        return match[1];
    }
    return null;
}

function cleanResponseText(response) {
    return response.replace(/\[IMAGE_REQUEST:(tongue|face|report)\]/, '').trim();
}

function getImagesData() {
    return {
        tongue_imgs: imageState.tongue.url ? [imageState.tongue.url] : [],
        face_imgs: imageState.face.url ? [imageState.face.url] : [],
        check_imgs: imageState.report.url ? [imageState.report.url] : []
    };
}

function clearAllImages() {
    ['tongue', 'face', 'report'].forEach(type => {
        if (imageState[type].file) {
            removeImage(type);
        }
    });
}