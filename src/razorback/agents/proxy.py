# ABOUTME: HTTP egress block — verbatim from run_experiment.py:1497-1525.
# ABOUTME: NO_PROXY exempts the anthropic + statsig + openai + pypi hosts the claude CLI needs.

# Verbatim copy of run_experiment.py:1509-1513. DO NOT paraphrase the host list — the smoke
# test (Task 1) asserts the path works with EXACTLY these hosts.
PROXY_EXEMPT_HOSTS = (
    ".anthropic.com,api.anthropic.com,statsig.anthropic.com,"
    "featuregates.org,.statsig.com,"
    ".openai.com,api.openai.com,auth.openai.com,chatgpt.com,"
    "pypi.org,files.pythonhosted.org,pypi.python.org"
)

# Verbatim copy of run_experiment.py:1515-1525.
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
