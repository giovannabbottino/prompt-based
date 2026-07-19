import os

from dotenv import load_dotenv
from flask import Flask

from .application.services import KnowledgeGraphService
from .controllers.analyze_controller import create_analyze_blueprint
from .infrastructure import OllamaClient, OllamaClientConfig, PromptRepository

DEFAULT_PROMPT_NAME = "prompts/few-shot.txt"
DEFAULT_SYSTEM_PROMPT_NAME = "system/knowledge_graph.txt"


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)

    prompt_repository = PromptRepository()
    env_default_prompt = os.getenv("DEFAULT_PROMPT_NAME", DEFAULT_PROMPT_NAME)
    env_default_system_prompt = os.getenv("DEFAULT_SYSTEM_PROMPT_NAME", DEFAULT_SYSTEM_PROMPT_NAME)

    ollama_config = OllamaClientConfig.from_env()
    ollama_client = OllamaClient(config=ollama_config)

    service = KnowledgeGraphService(
        prompt_repository,
        default_prompt=env_default_prompt,
        default_system_prompt=env_default_system_prompt,
        ollama_client=ollama_client,
    )
    app.register_blueprint(create_analyze_blueprint(service))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
