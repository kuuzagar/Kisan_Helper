import os
from sarvamai import SarvamAI

# load the key from .env into the environment (no extra package needed)
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_file):
    for line in open(env_file):
        if "=" in line and not line.startswith("#"):
            name, value = line.strip().split("=", 1)
            os.environ.setdefault(name, value)

api_key = os.environ.get("SARVAM_API_KEY")
if not api_key:
    raise SystemExit("SARVAM_API_KEY is empty - paste your key into .env first.")

client = SarvamAI(api_subscription_key=api_key)

response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "Say hello in Hindi and English in one line."}],
)

print(response.choices[0].message.content)
