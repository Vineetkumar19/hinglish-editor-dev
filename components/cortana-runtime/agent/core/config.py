"""Machine settings; local inference is the sole M1 backend."""
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = AGENT_DIR.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=AGENT_DIR / '.env', env_prefix='CORTANA_', extra='ignore')
    app_name: str = 'Cortana Agent'
    phase: int = 1
    host: str = '127.0.0.1'
    port: int = 8000
    cors_origins: list[str] = []
    ollama_host: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'cortana-local:9b'
    ollama_vision_model: str = 'qwen3-vl:8b-instruct-q4_K_M'
    ollama_timeout_seconds: float = 120.0
    ollama_backup_timeout_seconds: float = 20.0
    ollama_num_predict: int = 700
    ollama_num_ctx: int = 8192
    ollama_keep_alive: str = '5m'
    max_tool_rounds: int = 5
    conversation_history_turns: int = 6
    headroom_enabled: bool = False
    # Legacy credentials retained locally for a future reviewed consent flow.
    # These flags never authorize cloud transmission in this milestone.
    primary_backend: str = 'local'
    cloud_fallback_enabled: bool = False
    cloud_fallback_base_url: str = ''
    cloud_fallback_api_key: str = ''
    cloud_fallback_model: str = ''
    cloud_fallback_timeout_seconds: float = 30.0
    cloud_vision_enabled: bool = False
    stt_model_size: str = 'large-v3-turbo'
    stt_wake_model_size: str = 'large-v3-turbo'
    stt_device: str = 'cuda'
    stt_cpu_threads: int = 8
    stt_compute_type: str = 'int8_float16'
    stt_cpu_fallback_model_size: str = 'small'
    stt_preview_model_size: str = 'base'
    stt_language: str = 'auto'
    stt_local_files_only: bool = True
    stt_download_root: str = str(ROOT_DIR / 'models' / 'speech')
    stt_vad_filter: bool = True
    stt_vad_min_silence_ms: int = 400
    stt_initial_prompt: str = ('Cortana. English, Hindi, Hinglish. Chrome kholo, YouTube kholo, '
        'ChatGPT open karo. स्क्रीन पर यह error समझाओ। Downloads, Documents, Desktop, '
        'screenshot, Visual Studio Code, Vineet.')
    tts_rate: int = 180
    tts_voice_id: str = ''
    wake_word: str = 'cortana'
    memory_dir: str = str(ROOT_DIR / 'memory')
    documents_dir: str = str(ROOT_DIR / 'documents')
    poppler_bin: str = str(ROOT_DIR / '.runtime' / 'poppler' / 'Library' / 'bin')
    logs_dir: str = str(ROOT_DIR / 'logs')
    app_config_path: str = str(ROOT_DIR / 'config' / 'settings.json')
    app_config_example_path: str = str(ROOT_DIR / 'config' / 'settings.example.json')

    @field_validator('host')
    @classmethod
    def local_bind_only(cls, value: str) -> str:
        if value != '127.0.0.1':
            raise ValueError('Cortana must bind to 127.0.0.1')
        return value

    @field_validator('ollama_host')
    @classmethod
    def local_model_only(cls, value: str) -> str:
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {'', '/'}):
            raise ValueError('The M1 model endpoint must be local Ollama')
        return value.rstrip('/')

settings = Settings()
