export PYTHONDONTWRITEBYTECODE=1
export UV_PROJECT_ENVIRONMENT=/tmp/venv
uvx() { shift; uv run -q --frozen --project /labnotes/packages/python labnotes "$@"; }
uvx labnotes --version > /dev/null
unset GIT_DIR GIT_WORK_TREE
cp -r /labnotes/docs/demos/project /tmp/project
cd /tmp/project
clear
