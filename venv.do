
set -eu

redo-ifchange requirements.txt
exec >&2
rm -rf venv.dir
python3 -m venv ./venv.dir
. ./venv.dir/bin/activate

pip3 install --require-virtualenv -r requirements.txt

# Before 0.5, amaranth-soc points directly at Git head.
# To install with 0.4, we have to use --ignore-conflicts.
# Last version before 0.5 upgrade...
# but that's because it points directly at git.
# We want to keep 0.4, so --no-dependencies (to avoid upgrading).
pip3 install \
    --require-virtualenv \
    --no-dependencies \
    git+https://github.com/amaranth-lang/amaranth-soc@e1b842800533f44924f21c3867bc2290084d100f

ls venv.dir/ >"$3"
