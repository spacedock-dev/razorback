# ABOUTME: HTTP egress block derived from run_experiment.py:1497-1525.
# ABOUTME: NO_PROXY exempts the API, package, and dbt registry hosts agents need.

PROXY_EXEMPT_HOSTS = (
    ".anthropic.com,api.anthropic.com,statsig.anthropic.com,"
    "featuregates.org,.statsig.com,"
    ".openai.com,api.openai.com,auth.openai.com,chatgpt.com,"
    "pypi.org,files.pythonhosted.org,pypi.python.org,"
    "hub.getdbt.com,codeload.github.com"
)

PROXY_BLOCK_ENV: dict[str, str] = {
    "HTTP_PROXY": "http://127.0.0.1:1",
    "HTTPS_PROXY": "http://127.0.0.1:1",
    "http_proxy": "http://127.0.0.1:1",
    "https_proxy": "http://127.0.0.1:1",
    "NO_PROXY": PROXY_EXEMPT_HOSTS,
    "no_proxy": PROXY_EXEMPT_HOSTS,
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
}
