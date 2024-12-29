
set -eu

redo-ifchange requirements.txt
exec >&2
rm -rf venv.dir
python3 -m venv ./venv.dir
. ./venv.dir/bin/activate

pip3 install --require-virtualenv -r requirements.txt

# Requires amaranth=0.4; I'll try to hack around it.
pip3 install \
    --require-virtualenv \
    --no-dependencies \
    git+https://github.com/greatscottgadgets/luna.git@0.1.3

ls venv.dir/ >"$3"
