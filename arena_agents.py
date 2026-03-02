from abc import ABC, abstractmethod
import os, time, requests
from utils import DEFAULT_AGENT_TIMEOUT, call_with_timeout

from groq import Groq
from openai import OpenAI


class ArenaAgent(ABC):
    def __init__(self, config):
        self.config = config
        self.id = config["id"]
        self.name = config["name"]
        self.model = config["model"]
        self.timeout = config.get("timeout") or DEFAULT_AGENT_TIMEOUT
        
    @abstractmethod
    def _answer(self, question: str) -> str:
        """Actual model call (must be implemented)"""
        pass
        
    def answer(self, question: str):
      return call_with_timeout(
        lambda: self._answer(question),
        timeout=self.timeout
      )

class GroqAgent(ArenaAgent):
    def __init__(self, config):
        super().__init__(config)
        
        key_env = config.get("api_key_env")
        if not key_env:
            raise ValueError(f"Missing api_key_env for Groq agent: {self.name}")
            
        api_key = os.environ.get(key_env)    
        if not api_key:
            raise ValueError(f"Environment key not set: {key_env}")
            
        self.client = Groq(api_key=api_key)

    def _answer(self, question: str) -> str:
        try:
            r = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a quiz contestant. "
                            "Answer ONLY the final answer. "
                            "No explanation. "
                            "1 to 4 words maximum."
                        )
                    },
                    {"role": "user", "content": question}
                ],
                temperature=0,
                timeout=self.timeout - 1  # API timeout < hard timeout
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Groq error ({self.name}): {e}")
            self.config["last_error"] = str(e)
            return ""


class OpenAIAgent(ArenaAgent):
    def __init__(self, config):
        super().__init__(config)
        
        key_env = config.get("api_key_env")
        if not key_env:
            raise ValueError(f"Missing api_key_env for Groq agent: {self.name}")
            
        api_key = os.environ.get(key_env)    
        if not api_key:
            raise ValueError(f"Environment key not set: {key_env}")
            
        self.client = OpenAI(api_key=api_key)

    def _answer(self, question: str) -> str:
        try:
            r = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a quiz contestant. "
                            "Answer ONLY the final answer. "
                            "No explanation. "
                            "1 to 4 words maximum."
                        )
                    },
                    {"role": "user", "content": question}
                ],
                timeout=self.timeout - 1
            )
            return r.output_text.strip()
        except Exception as e:
            print(f"⚠️ OpenAI error ({self.name}): {e}")
#            self.config["last_error"] = "test short error"
            raise ValueError(str(e))
            return ""


class HttpAgent(ArenaAgent):
    def __init__(self, config):
        super().__init__(config)
        self.endpoint = config.get("endpoint")
        if not self.endpoint:
            raise ValueError(f"{self.name}: missing endpoint")

    def _answer(self, question: str) -> str:
        payload = {
            "question": question,
            "timeout": self.timeout
        }

        start = time.time()

        try:
            r = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout - 1  # keep < hard timeout
            )
            if "last_error" in self.config:
                del self.config["last_error"]
        except requests.exceptions.Timeout:
            print(f"⏱️ HTTP timeout ({self.name})")
            self.config["last_error"] = "timeout occurred"
            return ""

        except requests.exceptions.RequestException as e:
            print(f"🌐 HTTP network error ({self.name}): {e}")
            self.config["last_error"] = str(e)
            return ""

        latency_ms = int((time.time() - start) * 1000)

        if r.status_code != 200:
            print(f"❌ HTTP status {r.status_code} ({self.name})")
            self.config["last_error"] = "HTTP response status code: " + str(r.status_code)
            return ""

        try:
            data = r.json()
        except ValueError:
            print(f"⚠️ Invalid JSON ({self.name})")
            self.config["last_error"] = "response: invalid_json"
            return ""

        answer = data.get("answer")

        if not answer:
            print(f"⚠️ Missing answer field ({self.name})")
            self.config["last_error"] = "Missing answer field"
            return ""

        # Optional: if you want to capture agent-side latency
        agent_latency = data.get("latency_ms")
        if agent_latency is not None:
            self.config["last_latency_ms"] = agent_latency
        else:
            self.config["last_latency_ms"] = latency_ms

        return str(answer).strip()

