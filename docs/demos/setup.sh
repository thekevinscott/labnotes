export PYTHONDONTWRITEBYTECODE=1
export UV_PROJECT_ENVIRONMENT=/tmp/venv
uvx() { shift; uv run -q --frozen --project /labnotes/packages/python labnotes "$@"; }
cp -r /labnotes/docs/demos/project /tmp/project
cd /tmp/project
uvx labnotes experiments > /dev/null
clear
