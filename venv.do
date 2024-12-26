
set -eu

redo-ifchange requirements.txt
exec >&2
rm -rf venv.dir
python3 -m venv ./venv.dir
. ./venv.dir/bin/activate

pip3 install --require-virtualenv -r requirements.txt
ls venv.dir/ >"$3"
