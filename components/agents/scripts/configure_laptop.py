"""Apply the measured local model and confirmed work preferences; preserve credentials."""
from pathlib import Path
import json
import re
import secrets

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = {
    "LLM_PROVIDER": "ollama", "LLM_MODEL": "storylens-meaning:14b",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434", "OLLAMA_NUM_CTX": "8192",
    "OLLAMA_KEEP_ALIVE": "5m", "OLLAMA_NUM_GPU": "99", "OLLAMA_NUM_BATCH": "256",
    "OLLAMA_THINK": "false", "JOB_MIN_MONTHLY_INR": "50000",
    "FREELANCE_MIN_PROJECT_INR": "10000", "FREELANCE_MIN_PROJECT_USD": "150",
    "JOB_AUTO_APPLICATIONS": "true", "APPLICATION_ANSWERS_FILE": "D:/Agents/profiles/application_answers.yaml",
    "BROWSER_CHANNEL": "chrome", "BROWSER_HEADLESS": "true",
    "SPONSORSHIP_MAX_LEADS": "5", "VIDEO_CLIENT_MAX_LEADS": "5",
    "VIDEO_CLIENT_MAX_GIGS": "5", "DEV_CLIENT_MAX_GIGS": "5", "FULLSTACK_MAX_LEADS": "5",
    "JOB_MAX_PER_RUN": "5", "COMMUNITY_MAX_PER_RUN": "3", "FOLLOWUP_DAYS": "5", "FOLLOWUP_MAX": "2",
    "SCHEDULED_AGENTS": "community,sponsorship,video_client,fullstack_sales,job_hunter",
}


def main():
    path = ROOT / ".env"
    text = path.read_text(encoding="utf-8")
    if not re.search(r"(?m)^DASHBOARD_TOKEN=\S+", text):
        SETTINGS["DASHBOARD_TOKEN"] = secrets.token_urlsafe(32)
    for key, value in SETTINGS.items():
        pattern = rf"(?m)^{re.escape(key)}=.*$"
        if re.search(pattern, text):
            text = re.sub(pattern, lambda _: f"{key}={value}", text)
        else:
            text += f"\n{key}={value}\n"
    path.write_text(text, encoding="utf-8")
    hardware = {"computer": "ASUS ROG Strix G16 G614PR", "cpu": "AMD Ryzen 9 8940HX",
        "physical_cores": 16, "logical_processors": 32, "ram_gib": 15.2,
        "gpu": "NVIDIA GeForce RTX 5070 Ti Laptop GPU", "vram_mib": 12227,
        "model": SETTINGS["LLM_MODEL"], "context_tokens": 8192,
        "local_inference_concurrency": 1, "measured_on": "2026-10-20",
        "benchmark_file": "data/model-benchmark.json"}
    (ROOT / "data" / "laptop-profile.json").write_text(json.dumps(hardware, indent=2), encoding="utf-8")
    print("Applied local model settings and confirmed work preferences. Credentials preserved.")


if __name__ == "__main__":
    main()
