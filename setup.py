from setuptools import setup, find_packages

setup(
    name="fuse-guardrail",
    version="1.0.0",
    description="Autonomous AWS Cost Guardrail & Surgical WAF Circuit Breaker CLI",
    author="Pranjul Chaurasiya",
    py_modules=["fuse"],
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "fuse=cli.fuse:main",
        ],
    },
    install_requires=[
        "boto3>=1.34.0",
    ],
    python_requires=">=3.10",
)
