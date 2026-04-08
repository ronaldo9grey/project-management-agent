from setuptools import setup, find_packages

setup(
    name="project-agent-backend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "langchain>=0.1.0",
        "langgraph>=0.0.40",
        "langchain-openai>=0.0.5",
    ],
)